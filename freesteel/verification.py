#
#		FreeSteel
#		Certificate Verification
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

import datetime
import urllib.request

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import ExtensionOID, NameOID

from freesteel.exceptions import VerificationError, CertificateRevokedError

# certificate on card proves nothing on its own, anyone can make one with
# any name in it. it can be trusted only if it was signed by authority we
# already trust, or by authority which was in turn signed by a trusted
# one. this list of certificates, each signed by the next, is called chain:
#
#	certificate from card -> intermediate authority -> root authority
#
# root authority signs its own certificate, so it has to be obtained from
# a place we trust and given to verifier as trusted. authorities can also
# take back certificates before they expire, for example when card is
# lost, by publishing their serial numbers in signed revocation list

PEM_MARKER = b'-----BEGIN'  # text encoded files start with this, others are binary (DER)
MAX_CHAIN_LENGTH = 8  # protects from endless search in case authorities point to each other
DOWNLOAD_TIMEOUT = 60  # seconds
DOWNLOAD_SCHEMES = ('http://', 'https://')


def load_certificate(data):
	"""Load certificate from PEM or DER encoded data"""
	try:
		if data.lstrip().startswith(PEM_MARKER):
			result = x509.load_pem_x509_certificate(data)

		else:
			result = x509.load_der_x509_certificate(data)

	except ValueError as error:
		raise VerificationError('Error loading certificate: {0}'.format(error))

	return result

def load_revocation_list(data):
	"""Load certificate revocation list from PEM or DER encoded data"""
	try:
		if data.lstrip().startswith(PEM_MARKER):
			result = x509.load_pem_x509_crl(data)

		else:
			result = x509.load_der_x509_crl(data)

	except ValueError as error:
		raise VerificationError('Error loading revocation list: {0}'.format(error))

	return result

def get_revocation_list_addresses(data):
	"""Get addresses of revocation list on which certificate would be listed"""
	result = []
	certificate = load_certificate(data)

	# authority writes location of its revocation list in every certificate it issues
	try:
		extension = certificate.extensions.get_extension_for_oid(ExtensionOID.CRL_DISTRIBUTION_POINTS)

	except x509.ExtensionNotFound:
		return result

	# there can be more than one location, each can be given
	# in different ways and only addresses are of use to us
	for point in extension.value:
		for name in point.full_name or []:
			if isinstance(name, x509.UniformResourceIdentifier):
				result.append(name.value)

	return result

def download_revocation_list(data):
	"""Download revocation list on which certificate would be listed"""
	for address in get_revocation_list_addresses(data):
		# address comes from certificate, allow only web addresses
		if not address.lower().startswith(DOWNLOAD_SCHEMES):
			continue

		try:
			with urllib.request.urlopen(address, timeout=DOWNLOAD_TIMEOUT) as response:
				return response.read()

		except OSError:
			# try next address
			continue

	raise VerificationError('Error downloading revocation list: no address could be reached')


class Verifier:
	"""Verify certificates against trusted certificate authorities"""

	def __init__(self):
		self._trusted = []  # certificates trusted without checking who issued them
		self._intermediate = []  # certificates of authorities which need to be checked themselves
		self._revocation_lists = []

	def __get_name(self, certificate):
		"""Get short name of certificate for use in messages"""
		names = certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)

		if len(names) > 0:
			result = names[0].value

		else:
			result = 'with serial number {0:X}'.format(certificate.serial_number)

		return result

	def __is_issued_by(self, certificate, authority):
		"""Check if certificate was signed by authority"""
		# this checks that name of issuer written in certificate is name of
		# authority and that signature was made with authority's key. name
		# alone is not enough since anyone can put any name in certificate
		try:
			certificate.verify_directly_issued_by(authority)

		except (ValueError, TypeError, InvalidSignature):
			return False

		return True

	def __find_authority(self, certificate, authorities):
		"""Find authority which issued certificate"""
		for authority in authorities:
			if self.__is_issued_by(certificate, authority):
				return authority

		return None

	def __build_chain(self, certificate):
		"""Get list of certificates leading to trusted one"""
		result = [certificate]

		# climb from certificate to its issuer, then to
		# issuer's issuer, until trusted certificate is reached
		while len(result) <= MAX_CHAIN_LENGTH:
			current = result[-1]

			# trusted certificate ends the chain
			authority = self.__find_authority(current, self._trusted)
			if authority is not None:
				result.append(authority)
				return result

			# no issuer means we know nothing about who made this certificate,
			# seeing the same one twice means authorities issued each other
			authority = self.__find_authority(current, self._intermediate)
			if authority is None or authority in result:
				name = self.__get_name(current)
				raise VerificationError('Certificate {0} was not issued by trusted authority'.format(name))

			result.append(authority)

		raise VerificationError('Certificate chain is too long')

	def __check_dates(self, certificate, moment):
		"""Make sure certificate is valid at specified moment"""
		name = self.__get_name(certificate)

		if moment < certificate.not_valid_before_utc:
			raise VerificationError('Certificate {0} is not valid yet'.format(name))

		if moment > certificate.not_valid_after_utc:
			raise VerificationError('Certificate {0} has expired'.format(name))

	def __check_authority(self, authority, authorities_below):
		"""Make sure certificate is allowed to issue other certificates"""
		name = self.__get_name(authority)
		extensions = authority.extensions

		# without this check owner of any valid certificate, like the
		# one on card, could issue certificates which would be trusted
		try:
			constraints = extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS).value

		except x509.ExtensionNotFound:
			constraints = None

		if constraints is None or not constraints.ca:
			raise VerificationError('Certificate {0} is not certificate authority'.format(name))

		# authority can be limited in how many levels of
		# other authorities are allowed between it and certificate
		if constraints.path_length is not None and constraints.path_length < authorities_below:
			raise VerificationError('Certificate {0} is not allowed this many authorities below it'.format(name))

		try:
			usage = extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE).value

		except x509.ExtensionNotFound:
			# usage is not restricted
			return

		if not usage.key_cert_sign:
			raise VerificationError('Certificate {0} is not allowed to issue certificates'.format(name))

	def __find_revocation_list(self, authority):
		"""Find newest revocation list issued by authority"""
		result = None

		for revocation_list in self._revocation_lists:
			if revocation_list.issuer != authority.subject:
				continue

			# list has to be signed by authority, otherwise anyone
			# could hide revoked certificate by supplying empty list
			if not revocation_list.is_signature_valid(authority.public_key()):
				continue

			# authority publishes new list regularly, only the last one counts
			if result is None or revocation_list.last_update_utc > result.last_update_utc:
				result = revocation_list

		return result

	def __check_revocation(self, certificate, authority, moment):
		"""Make sure authority did not revoke certificate"""
		name = self.__get_name(certificate)
		authority_name = self.__get_name(authority)
		revocation_list = self.__find_revocation_list(authority)

		# missing list is treated as failure, since it
		# can't be said that certificate is still good
		if revocation_list is None:
			raise VerificationError('Revocation list issued by {0} is missing'.format(authority_name))

		# list says when the next one will be published, after that
		# moment it might no longer contain everything that was revoked
		next_update = revocation_list.next_update_utc
		if next_update is not None and moment > next_update:
			raise VerificationError('Revocation list issued by {0} is out of date'.format(authority_name))

		# revoked certificates are listed by their serial numbers
		if revocation_list.get_revoked_certificate_by_serial_number(certificate.serial_number) is not None:
			raise CertificateRevokedError('Certificate {0} has been revoked'.format(name))

	def add_trusted_certificate(self, data):
		"""Add certificate which is trusted without further checks, usually root authority"""
		self._trusted.append(load_certificate(data))

	def add_intermediate_certificate(self, data):
		"""Add certificate of authority which has to lead to trusted one"""
		self._intermediate.append(load_certificate(data))

	def add_revocation_list(self, data):
		"""Add list of certificates revoked by one of authorities"""
		self._revocation_lists.append(load_revocation_list(data))

	def get_chain(self, data):
		"""Get DER encoded certificates leading from the given one to trusted one"""
		# only signatures are checked here, use verify to find
		# out if certificates in chain can actually be trusted
		chain = self.__build_chain(load_certificate(data))

		return [current.public_bytes(Encoding.DER) for current in chain]

	def verify(self, data, check_revocation=True, moment=None):
		"""Verify certificate and return its chain as names, raise error when it can't be trusted"""
		certificate = load_certificate(data)

		# certificate is checked as of this moment, which allows asking
		# if it was good at some point in past, like when document was signed
		if moment is None:
			moment = datetime.datetime.now(datetime.timezone.utc)

		# this fails unless certificate leads to trusted one through valid signatures
		chain = self.__build_chain(certificate)

		for index, current in enumerate(chain):
			self.__check_dates(current, moment)

			# first certificate is the one being verified, others are authorities
			if index > 0:
				self.__check_authority(current, index - 1)

		# every certificate except trusted one has to be checked with its authority
		if check_revocation:
			for current, authority in zip(chain[:-1], chain[1:]):
				self.__check_revocation(current, authority, moment)

		return [self.__get_name(current) for current in chain]
