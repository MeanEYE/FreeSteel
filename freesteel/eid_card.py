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

from card import Card, CardCommand as Command


class CardFile:
	DOCUMENT = (0x0F, 0x02)  # Document data
	PERSONAL = (0x0F, 0x03)  # Personal data
	RESIDENCE = (0x0F, 0x04)  # Place of residence, variable length
	PHOTO = (0x0F, 0x06)  # Personal photo in JPEG format
	CERT_QUALIFIED = (0x0F, 0x10)  # Public X.509 certificate for qualified (Non Repudiation) signing
	CERT_STANDARD = (0x0F, 0x08)  # Public X.509 certificate for standard signing


class DocumentField:
	ID = 10
	TYPE = 11
	TYPE2 = 12
	RELEASE_DATE = 13
	VALID_UNTIL = 14
	ISSUER = 15
	ISSUER_COUNTRY = 9
	UNKNOWN_FIELD_1 = 16
	UNKNOWN_FIELD_2 = 17


class PersonalField:
	PIN = 22
	LAST_NAME = 23
	FIRST_NAME = 24
	MIDDLE_NAME = 25
	SEX = 26
	BIRTH_PLACE = 27
	BIRTH_MUNICIPAL = 28
	BIRTH_COUNTRY = 29
	BIRTH_COUNTRY_CODE = 31
	DATE_OF_BIRTH = 30


class ResidenceField:
	COUNTRY_CODE = 32
	PLACE = 33
	MUNICIPAL = 34
	STREET = 35
	NUMBER = 36


class EidCard:
	"""Wrapper class used for reading electronic ID cards"""

	def __init__(self, card):
		self._card = card

	def __split_fields(self, data):
		"""Split fields and return dictionary"""
		result = {}

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

		for name, value in fields.items():
			fields[name] = scard_util.toASCIIString(value)

		return fields

	def __get_fields_from_file(self, card_file):
		"""Get fields from binary file and format them"""
		header, data = self._card.read_file(card_file)
		return self.__get_fields(data)

	def get_data_0101(self):
		"""Get 0101 data and format it"""
		return scard_util.toHexString(
							self._card.get_data(Command.GET_DATA_0101),
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

	def get_photo(self, filename=None):
		"""Return or save photo from electronic ID"""
		header, data = self._card.read_file(CardFile.PHOTO)
		data = scard_util.toASCIIString(data[4:])

		return data

	def get_qualified_certificate(self):
		"""Get qualified certificate data from the card"""
		pass

	def get_certificate(self):
		"""Get standard certificate data from the card"""
		pass
