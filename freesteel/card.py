#
#		FreeSteel
#		Card Implementation
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

import zlib
import smartcard.scard as scard

from freesteel.exceptions import GetDataError, SelectPathError, DisconnectCardError


# every command sent to card is a list of bytes in this order:
#
#	class, instruction, parameter 1, parameter 2, [data length, data], [expected length]
#
# parts in brackets are optional. card answers with data followed by
# two status bytes. classes below give names to values used in commands
# and responses, format itself is defined by ISO 7816-4 standard


# first byte of command, tells which set of instructions is used
class CommandClass:
	ISO = 0x00  # standard ISO 7816-4 command


# second byte of command, what card is asked to do
class Instruction:
	SELECT = 0xA4  # select file or application
	READ_BINARY = 0xB0  # read data from selected file
	GET_DATA = 0xCA  # get data object


# first parameter of select instruction, how the target is addressed
class SelectBy:
	FILE_IDENTIFIER = 0x00  # select file in current application by its identifier
	APPLICATION_NAME = 0x04  # select application by its identifier (AID)
	PATH = 0x08  # select file by path from master file


# second parameter of select instruction, what card should answer with
class SelectResponse:
	FILE_CONTROL_INFORMATION = 0x00  # return information about selected file


# first of two status bytes at the end of every response, second
# byte carries details like amount of data left or reason for error
class Status:
	SUCCESS = 0x90  # command completed
	MORE_DATA = 0x61  # command completed, more data is available
	WARNING_UNCHANGED = 0x62  # warning, card memory is unchanged
	WARNING_CHANGED = 0x63  # warning, card memory has changed

	# statuses after which response can be used
	ACCEPTED = (SUCCESS, MORE_DATA, WARNING_UNCHANGED, WARNING_CHANGED)


# data objects are small values stored outside of files, addressed
# with two bytes sent as parameters of get data instruction
class DataObject:
	UNKNOWN_0101 = (0x01, 0x01)  # purpose unknown, 32 bytes long


class Command:
	"""Builder for all commands sent to card"""

	MAX_LENGTH = 0xFF  # largest amount of data card returns in one response
	ANY_LENGTH = 0x00  # let card decide how much data to return

	@staticmethod
	def select_path(path, response_length):
		"""Select file by path"""
		# path is made of file identifiers leading from the top of
		# card's file system to the file, two bytes each
		command = [
			CommandClass.ISO,
			Instruction.SELECT,
			SelectBy.PATH,
			SelectResponse.FILE_CONTROL_INFORMATION,
			len(path)
		]
		command.extend(path)

		# number of bytes of information about file we want back
		command.append(response_length)

		return command

	@staticmethod
	def select_file(identifier):
		"""Select file in current application, without asking for response"""
		# unlike path, identifier is looked up only inside of
		# application which was selected before this command
		command = [
			CommandClass.ISO,
			Instruction.SELECT,
			SelectBy.FILE_IDENTIFIER,
			SelectResponse.FILE_CONTROL_INFORMATION,
			len(identifier)
		]
		command.extend(identifier)

		return command

	@staticmethod
	def select_application(name, response_length=ANY_LENGTH):
		"""Select application by its identifier, no response is asked for when length is None"""
		# card can hold many applications, each with its own set of
		# files, and only files of selected one can be accessed
		command = [
			CommandClass.ISO,
			Instruction.SELECT,
			SelectBy.APPLICATION_NAME,
			SelectResponse.FILE_CONTROL_INFORMATION,
			len(name)
		]
		command.extend(name)

		if response_length is not None:
			command.append(response_length)

		return command

	@staticmethod
	def read_binary(offset, length):
		"""Read part of selected file"""
		# position in file is sent in parameters, split in
		# two bytes with higher one first
		return [
			CommandClass.ISO,
			Instruction.READ_BINARY,
			offset >> 8,
			offset & 0xFF,
			length
		]

	@staticmethod
	def get_data(data_object, length):
		"""Get data object"""
		return [
			CommandClass.ISO,
			Instruction.GET_DATA,
			data_object[0],
			data_object[1],
			length
		]


class Card:
	"""Wrapper class for smart cards"""

	HEADER_LENGTH = 6  # size of header at the beginning of each file
	SELECT_RESPONSE_LENGTH = 1  # amount of file information to ask for

	def __init__(self, handle, protocol):
		# both are given by reader once it connects to card
		self._handle = handle
		self._protocol = protocol

	def _check_status(self, response, error_class, description):
		"""Raise error if status word in response is not successful"""
		# status is always in the last two bytes of response
		if len(response) < 2:
			raise error_class('{0}: card returned no status'.format(description))

		# first status byte tells if command worked
		if response[-2] not in Status.ACCEPTED:
			status = '{0:02X} {1:02X}'.format(response[-2], response[-1])
			raise error_class('{0}: card returned status {1}'.format(description, status))

	def _transmit(self, command, error_class, description):
		"""Send command to card and return checked response"""
		# send command through reader and wait for card to answer
		result, response = scard.SCardTransmit(
			self._handle,
			self._protocol,
			command
		)

		# result only tells if reader managed to exchange data with card
		if result != scard.SCARD_S_SUCCESS:
			message = scard.SCardGetErrorMessage(result)
			raise error_class('{0}: {1}'.format(description, message))

		# card reports its own errors through status in response
		self._check_status(response, error_class, description)

		return response

	def get_data(self, command):
		"""Get data from card"""
		response = self._transmit(command, GetDataError, 'Error reading card')

		# remove status word
		return response[:-2]

	def select_application(self, name, response_length=Command.ANY_LENGTH):
		"""Select application on card"""
		command = Command.select_application(name, response_length)
		return self._transmit(command, SelectPathError, 'Error selecting application')

	def select_file(self, identifier):
		"""Select file in current application"""
		command = Command.select_file(identifier)
		return self._transmit(command, SelectPathError, 'Error selecting file')

	def select_path(self, path):
		"""Select path on card"""
		command = Command.select_path(path, self.SELECT_RESPONSE_LENGTH)
		return self._transmit(command, SelectPathError, 'Error selecting path')

	def read_binary(self, offset, limit):
		"""Read binary data from card _after_ selecting path"""
		data = []
		end_position = offset + limit
		current_position = offset

		# card returns limited amount of data per command,
		# so anything bigger is read in small chunks
		while current_position < end_position:
			length = min(end_position - current_position, Command.MAX_LENGTH)
			command = Command.read_binary(current_position, length)

			chunk = self.get_data(command)
			if len(chunk) == 0:
				# card has no more data
				break

			# card is allowed to return less than what was asked
			# for, continue from where its answer has ended
			data.extend(chunk)
			current_position += len(chunk)

		return data

	def read_file(self, card_file):
		"""Select and read file from card"""
		# reading always works on file which was selected last
		self.select_path(card_file)

		# get header, its last two bytes hold size of
		# data which follows, with lower byte first
		header = self.read_binary(0, self.HEADER_LENGTH)
		file_size = (header[5] << 8) + header[4]

		# get data
		data = self.read_binary(self.HEADER_LENGTH, file_size)

		return header, data

	def read_certificates(self):
		"""Read certificates from card"""
		# these cards keep certificates in regular files, see
		# CardFile, but format of those files was never confirmed
		raise NotImplementedError('Reading certificates is not supported on this card')

	def disconnect(self):
		"""Safely disconnect card"""
		# power down the card, handle can't be used after this
		result = scard.SCardDisconnect(self._handle, scard.SCARD_UNPOWER_CARD)

		if result != scard.SCARD_S_SUCCESS:
			# failed disconnecting card
			message = scard.SCardGetErrorMessage(result)
			raise DisconnectCardError('Error disconnecting card: {0}'.format(message))


class GemaltoCard(Card):
	"""Wrapper class for Gemalto smart cards"""

	# these cards have shorter file header than the old ones
	HEADER_LENGTH = 4
	SELECT_RESPONSE_LENGTH = 4

	# document data is stored in one of three applications, depending
	# on type of document. only "SERID" was seen on a real card, the
	# other two are presumably documents issued to foreign citizens

	# application identifier, contains text "SERID"
	APPLICATION_NAME_ID = [
		0xF3, 0x81, 0x00, 0x00, 0x02, 0x53, 0x45,
		0x52, 0x49, 0x44, 0x01
	]

	# application identifier, contains text "SERIF"
	APPLICATION_NAME_IF = [
		0xF3, 0x81, 0x00, 0x00, 0x02, 0x53, 0x45,
		0x52, 0x49, 0x46, 0x01
	]

	# application identifier, contains text "SERRP"
	APPLICATION_NAME_RP = [
		0xF3, 0x81, 0x00, 0x00, 0x02, 0x53, 0x45,
		0x52, 0x52, 0x50, 0x01
	]

	# cryptography application identifier, contains text "PKCS-15"
	APPLICATION_NAME_CRYPTOGRAPHY = [
		0xA0, 0x00, 0x00, 0x00, 0x63, 0x50, 0x4B,
		0x43, 0x53, 0x2D, 0x31, 0x35
	]

	# files in cryptography application
	CERTIFICATE_FILES = (
		(0x71, 0x02),
		(0x71, 0x03)
	)
	CERTIFICATE_HEADER_LENGTH = 6  # size of header in front of compressed certificate

	# applications in order in which they are tried
	APPLICATION_NAMES = (
		APPLICATION_NAME_ID,
		APPLICATION_NAME_IF,
		APPLICATION_NAME_RP
	)

	def __init__(self, handle, protocol):
		Card.__init__(self, handle, protocol)

		# files are available only after selecting application
		self.application_name = self.__select_first_application()

	def __select_first_application(self):
		"""Select first application available on card"""
		# card answers with error when asked for application
		# it doesn't have, so they are simply tried in order
		for name in self.APPLICATION_NAMES:
			try:
				self.select_application(name)

			except SelectPathError:
				# card doesn't have this application
				continue

			return name

		raise SelectPathError('Error selecting application: card has no known application')

	def __read_certificate(self, card_file):
		"""Read and decompress certificate from selected cryptography application"""
		self.select_file(card_file)

		# content length (2 bytes, little-endian), not counting itself
		header = self.read_binary(0, 2)
		if len(header) < 2:
			raise GetDataError('Error reading card: certificate header is incomplete')

		# read whole file from the beginning, length included
		length = (header[1] << 8) + header[0] + 2
		data = self.read_binary(0, length)

		if len(data) <= self.CERTIFICATE_HEADER_LENGTH:
			raise GetDataError('Error reading card: certificate file is too short')

		# everything after header is certificate compressed with zlib
		try:
			certificate = zlib.decompress(bytes(data[self.CERTIFICATE_HEADER_LENGTH:]))

		except zlib.error as error:
			raise GetDataError('Error reading card: {0}'.format(error))

		return certificate

	def read_certificates(self):
		"""Read certificates from card as list of DER encoded X.509 certificates"""
		result = []

		# certificates are stored in separate application, selecting
		# it makes files with document data unavailable until we return
		self.select_application(self.APPLICATION_NAME_CRYPTOGRAPHY, None)

		try:
			for card_file in self.CERTIFICATE_FILES:
				try:
					result.append(self.__read_certificate(card_file))

				except (SelectPathError, GetDataError):
					# card doesn't have this certificate, they are
					# issued on request so many cards have one or none
					continue

		finally:
			# return to application containing document data
			self.select_application(self.application_name)

		return result

	def read_file(self, card_file, strip_tag=False):
		"""Select and read file from card"""
		self.select_path(card_file)

		# outer tag (2 bytes) followed by content length (2 bytes, little-endian)
		header = self.read_binary(0, self.HEADER_LENGTH)
		if len(header) < self.HEADER_LENGTH:
			raise GetDataError('Error reading card: file header is incomplete')

		length = (header[3] << 8) + header[2]
		offset = len(header)

		# read content in chunks, card returns limited amount of data at a time
		output = []
		while length > 0:
			data = self.read_binary(offset, length)
			if len(data) == 0:
				raise GetDataError('Error reading card: unexpected end of file')

			output.extend(data)
			offset += len(data)
			length -= len(data)

		# optionally skip inner tag and its length
		if strip_tag:
			output = output[4:]

		return header, output
