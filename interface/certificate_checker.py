#
#		FreeSteel
#		Certificate Checker
#
#		Copyright (c) 2026. by Mladen Mijatov <meaneye.rcf@gmail.com>
#
#		This program is free software; you can redistribute it and/or modify
#		it under the terms of the GNU General Public License as published by
#		the Free Software Foundation; either version 3 of the License, or
#		(at your option) any later version.
#
#		This program is distributed in the hope that it will be useful,
#		but WITHOUT ANY WARRANTY; without even the implied warranty of
#		MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#		GNU General Public License for more details.
#
#		You should have received a copy of the GNU General Public License
#		along with this program; if not, write to the Free Software
#		Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#		MA 02110-1301, USA.

import os
import pkgutil
import hashlib
import datetime

from threading import Thread
from gi.repository import GLib

from freesteel.verification import Verifier, load_revocation_list
from freesteel.verification import get_revocation_list_addresses, download_revocation_list
from freesteel.exceptions import VerificationError, CertificateRevokedError


class CheckStatus:
	VERIFYING = 0  # chain is being verified, nothing is known yet
	TRUSTED = 1  # issued by trusted authority, revocation was not checked
	CHECKING_REVOCATION = 2  # issued by trusted authority, revocation is being checked
	VALID = 3  # issued by trusted authority and not revoked
	UNCHECKED = 4  # issued by trusted authority, revocation could not be checked
	INVALID = 5  # not issued by trusted authority, expired or revoked


class CertificateChecker:
	"""Verify certificates from card without blocking the interface

	Handlers are given status, message explaining it and chain, which is list of
	DER encoded certificates from the checked one to trusted one, or None when
	chain is not known.

	"""

	# certificates of authorities issuing certificates found on cards, published
	# by ministry at https://ca.mup.gov.rs/ca/ca_lat/start/ca_crl/
	AUTHORITIES_DIRECTORY = 'authorities'
	TRUSTED_FILES = ('MUPRootCA4.crt',)
	INTERMEDIATE_FILES = ('MUPGradjaniCA4.crt', 'MUPStranciCA4.crt')

	CACHE_DIRECTORY = os.path.join(GLib.get_user_cache_dir(), 'freesteel')

	def __init__(self):
		self._trusted = [self.__read_authority(name) for name in self.TRUSTED_FILES]
		self._intermediate = [self.__read_authority(name) for name in self.INTERMEDIATE_FILES]

	def __read_authority(self, file_name):
		"""Read certificate of authority which comes with the program"""
		# files are read through package they are in, since program
		# can be started from single file where they can't be opened
		return pkgutil.get_data('interface', '{0}/{1}'.format(self.AUTHORITIES_DIRECTORY, file_name))

	def __create_verifier(self):
		"""Create verifier knowing all authorities"""
		result = Verifier()

		for data in self._trusted:
			result.add_trusted_certificate(data)

		for data in self._intermediate:
			result.add_intermediate_certificate(data)

		return result

	def __get_cached_list(self, path):
		"""Get revocation list saved earlier or None when new one is needed"""
		try:
			with open(path, 'rb') as raw_file:
				data = raw_file.read()

			revocation_list = load_revocation_list(data)

		except (OSError, VerificationError):
			# nothing was saved or what was saved can't be used
			return None

		# list tells when the next one is published, until then
		# downloading it again would get us the same thing
		next_update = revocation_list.next_update_utc
		now = datetime.datetime.now(datetime.timezone.utc)

		if next_update is None or now > next_update:
			return None

		return data

	def __get_revocation_list(self, certificate):
		"""Get list on which certificate would be if it was revoked, None when it names no list"""
		addresses = get_revocation_list_addresses(certificate)
		if len(addresses) == 0:
			return None

		# lists are big, the one for citizens is around 30 megabytes,
		# so they are kept between runs under name made from address
		file_name = hashlib.sha256(addresses[0].encode('utf-8')).hexdigest() + '.crl'
		path = os.path.join(self.CACHE_DIRECTORY, file_name)

		result = self.__get_cached_list(path)
		if result is not None:
			return result

		result = download_revocation_list(certificate)

		try:
			# write to the side first so list which is cut
			# short is never left in place of complete one
			os.makedirs(self.CACHE_DIRECTORY, exist_ok=True)

			with open(path + '.part', 'wb') as raw_file:
				raw_file.write(result)

			os.replace(path + '.part', path)

		except OSError:
			# list can still be used this time
			pass

		return result

	def __check_chain(self, certificate, report):
		"""Find out if certificate leads to trusted authority"""
		verifier = self.__create_verifier()
		report(CheckStatus.VERIFYING, 'Verifying chain')

		# this needs nothing but authorities which come with
		# the program, so nothing is downloaded or sent anywhere
		try:
			chain = verifier.verify(certificate, check_revocation=False)

		except VerificationError as error:
			report(CheckStatus.INVALID, str(error))
			return

		# first in chain is certificate itself, the rest are authorities
		# starting with the one which issued it and ending with trusted one
		message = 'Issued by {0}, not checked for revocation'.format(chain[1])
		report(CheckStatus.TRUSTED, message, verifier.get_chain(certificate))

	def __check_revocation(self, certificate, report):
		"""Find out if certificate was revoked, reporting how far it got"""
		verifier = self.__create_verifier()

		try:
			chain = verifier.verify(certificate, check_revocation=False)

		except VerificationError as error:
			report(CheckStatus.INVALID, str(error))
			return

		authority = chain[1]
		chain = verifier.get_chain(certificate)
		report(CheckStatus.CHECKING_REVOCATION, 'Issued by {0}, checking if it was revoked'.format(authority), chain)

		# lists are needed for certificate and for every authority
		# between it and trusted one, which this also covers
		try:
			for data in [certificate] + self._intermediate:
				revocation_list = self.__get_revocation_list(data)

				if revocation_list is not None:
					verifier.add_revocation_list(revocation_list)

			verifier.verify(certificate)

		except CertificateRevokedError as error:
			report(CheckStatus.INVALID, str(error), chain)

		except VerificationError as error:
			# usually there is no connection to download the list
			message = 'Issued by {0}, but it is not known if it was revoked. {1}'.format(authority, error)
			report(CheckStatus.UNCHECKED, message, chain)

		else:
			report(CheckStatus.VALID, 'Valid, issued by {0}'.format(authority), chain)

	def __call_handler(self, handler, arguments):
		"""Call handler, executed in main thread"""
		handler(*arguments)

		# returning false prevents this from being called again
		return False

	def __run(self, method, certificate, handler):
		"""Execute one of the checks, executed in separate thread"""
		def report(status, message, chain=None):
			# interface must not be touched from this thread
			GLib.idle_add(self.__call_handler, handler, (status, message, chain))

		try:
			method(certificate, report)

		except Exception as error:
			# make sure certificate is never left looking like it is being checked
			report(CheckStatus.UNCHECKED, 'Certificate could not be checked. {0}'.format(error))

	def __start(self, method, certificate, handler):
		"""Start one of the checks without blocking the interface"""
		# thread of this kind doesn't keep program alive once window is closed
		thread = Thread(target=self.__run, args=(method, certificate, handler), daemon=True)
		thread.start()

	def check_chain(self, certificate, handler):
		"""Start verifying chain of certificate, handler(status, message, chain) is called with result"""
		self.__start(self.__check_chain, certificate, handler)

	def check_revocation(self, certificate, handler):
		"""Start finding out if certificate was revoked, handler(status, message, chain) is called with progress"""
		# this downloads list of revoked certificates unless recent one
		# was saved, which is why it is only done when user asks for it
		self.__start(self.__check_revocation, certificate, handler)
