#
#		FreeSteel
#		Electronic Id Information Parser
#
#		Copyright (c) 2011. by Mladen Mijatov <meaneye.rcf@gmail.com>
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

import smartcard.util as scard_util

from freesteel.card import Command, DataObject


# bytes used for finding key usage inside of certificate, which
# tells what the certificate is allowed to be used for
KEY_USAGE_IDENTIFIER = bytes([0x06, 0x03, 0x55, 0x1D, 0x0F])  # object identifier 2.5.29.15
KEY_USAGE_CRITICAL = bytes([0x01, 0x01, 0xFF])  # flag saying usage must not be ignored
KEY_USAGE_NON_REPUDIATION = 0x40  # bit set when signatures can't be denied later


# files on card, each identified with two bytes. these are not part of
# any standard, they were chosen by issuer of the card and are known
# only from other open source projects reading the same card
class CardFile:
	DOCUMENT = (0x0F, 0x02)
	PERSONAL = (0x0F, 0x03)
	RESIDENCE = (0x0F, 0x04)
	PHOTO = (0x0F, 0x06)

	# certificates on Apollo cards, Gemalto cards keep them in cryptography application
	CERT_QUALIFIED = (0x0F, 0x10)  # Public X.509 certificate for qualified (Non Repudiation) signing
	CERT_STANDARD = (0x0F, 0x08)  # Public X.509 certificate for standard signing
	CERT_INTERMEDIATE = (0x0F, 0x11)  # Public X.509 certificate of intermediate certificate authority


# files with data are made of fields, each marked with a number. classes
# below name the numbers found in each file. not all fields exist on
# all cards, so their presence should be checked before use


# fields in file with data about the document itself
class DocumentField:
	ID = 10
	TYPE = 11
	SERIAL_NUMBER = 12
	RELEASE_DATE = 13
	VALID_UNTIL = 14
	ISSUER = 15
	ISSUER_COUNTRY = 9
	UNKNOWN_FIELD_1 = 16
	UNKNOWN_FIELD_2 = 17
	CHIP_SERIAL_NUMBER = 145
	NAME = 146


# fields in file with data about person document was issued to
class PersonalField:
	PIN = 22
	LAST_NAME = 23
	FIRST_NAME = 24
	PARENT_NAME = 25
	SEX = 26
	BIRTH_PLACE = 27
	BIRTH_MUNICIPAL = 28
	BIRTH_COUNTRY = 29
	BIRTH_COUNTRY_CODE = 31
	DATE_OF_BIRTH = 30
	PURPOSE_OF_STAY_OLD = 46  # used when PURPOSE_OF_STAY is missing
	NATIONALITY = 47
	PURPOSE_OF_STAY = 147
	NOTE = 148


# fields in file with address of the person
class ResidenceField:
	COUNTRY_CODE = 32
	MUNICIPAL = 33
	PLACE = 34
	STREET = 35
	NUMBER = 36
	LETTER = 37
	ENTRANCE = 38
	FLOOR = 39
	APARTMENT = 42
	ADDRESS_DATE = 44
	ADDRESS_LABEL = 45


class EidCard:
	"""Wrapper class used for reading electronic ID cards"""

	def __init__(self, card):
		# card object does the communication, this class
		# only knows where data is and how to read it
		self._card = card

	def __split_fields(self, data):
		"""Split fields and return dictionary"""
		result = {}

		# file is made of fields placed one after the other:
		#
		#	number (2 bytes), length (2 bytes), value (length bytes)
		#
		# both number and length have lower byte first. only that byte
		# is used here, which limits value to 255 bytes

		# split fields
		position = 0
		while position < len(data):
			# get data from stream
			field = data[position]
			length = data[position+2]
			value = data[position+4:position+4+length]

			# add field to result
			result[field] = value

			# increase position
			position += 4 + length

		return result

	def __get_fields(self, data):
		"""Get fields in human readable format"""
		fields = self.__split_fields(data)

		# values are text encoded as UTF-8, bytes which are
		# not valid are replaced instead of failing whole file
		for name, value in fields.items():
			fields[name] = bytes(value).decode('utf-8', 'replace')

		return fields

	def __get_fields_from_file(self, card_file):
		"""Get fields from binary file and format them"""
		# file header is not needed, only its content
		data = self._card.read_file(card_file)[1]
		return self.__get_fields(data)

	def get_data_0101(self):
		"""Get 0101 data and format it"""
		# meaning of this data is unknown, command comes from old
		# cards and is rejected by newer Gemalto ones
		command = Command.get_data(DataObject.UNKNOWN_0101, 0x20)

		return scard_util.toHexString(
							self._card.get_data(command),
							scard_util.PACK
						)

	def get_document(self):
		"""Get document data from card"""
		return self.__get_fields_from_file(CardFile.DOCUMENT)

	def get_personal(self):
		"""Get document owner personal data from card"""
		return self.__get_fields_from_file(CardFile.PERSONAL)

	def get_residence(self):
		"""Get document owner's residence data from card"""
		return self.__get_fields_from_file(CardFile.RESIDENCE)

	def get_photo(self):
		"""Return or save photo from electronic ID"""
		data = self._card.read_file(CardFile.PHOTO)[1]

		# content starts with four more bytes of header, rest is JPEG image
		return bytes(data[4:])

	def __is_qualified(self, certificate):
		"""Check if certificate key usage allows non repudiation"""
		# certificate is not parsed, key usage is instead located by
		# searching for its identifier to avoid depending on other libraries
		position = certificate.find(KEY_USAGE_IDENTIFIER)
		if position == -1:
			return False

		position += len(KEY_USAGE_IDENTIFIER)

		# skip optional flag marking extension as critical
		if certificate[position:position+3] == KEY_USAGE_CRITICAL:
			position += 3

		# value is bit string wrapped in octet string, two bytes of
		# header each, followed by number of unused bits and flags
		flags = certificate[position+5:position+6]
		if len(flags) == 0:
			return False

		return flags[0] & KEY_USAGE_NON_REPUDIATION != 0

	def get_certificates(self):
		"""Get all certificates from card as DER encoded X.509"""
		return self._card.read_certificates()

	def get_qualified_certificate(self):
		"""Get certificate for qualified (non repudiation) signing or None"""
		# card doesn't tell which certificate is which, so they
		# are told apart by what they are allowed to be used for
		for certificate in self.get_certificates():
			if self.__is_qualified(certificate):
				return certificate

		return None

	def get_certificate(self):
		"""Get certificate for standard signing or None"""
		for certificate in self.get_certificates():
			if not self.__is_qualified(certificate):
				return certificate

		return None
