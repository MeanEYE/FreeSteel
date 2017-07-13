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

import smartcard.scard as scard

from exceptions import GetDataError, SelectPathError, DisconnectCardError

class CardCommand:
	GET_DATA_0101 = [0x00, 0xCA, 0x01, 0x01, 0x20]
	SELECT_PATH = [0x00, 0xA4, 0x08, 0x00]
	READ_BINARY = [0x00, 0xB0]


class Card:
	"""Wrapper class for smart cards"""

	def __init__(self, handle, protocol):
		self._handle = handle
		self._protocol = protocol

	def get_data(self, command):
		"""Get data from card"""
		data = None

		# get data from card
		result, response = scard.SCardTransmit(
			self._handle,
			self._protocol,
			command
		)

		# raise error if needed
		if result != scard.SCARD_S_SUCCESS:
			# failed reading data from card
			message = scard.SCardGetErrorMessage(result)
			raise GetDataError('Error reading card: {0}'.format(message))

		else:
			data = response

		return data[:-2]

	def select_path(self, path):
		"""Select path on card"""
		request = CardCommand.SELECT_PATH[:]
		request.append(len(path))
		request.extend(path)
		request.append(0x01)

		# transmit command to card
		result, response = scard.SCardTransmit(
			self._handle,
			self._protocol,
			request
		)

		# raise error if needed
		if result != scard.SCARD_S_SUCCESS:
			# failed selecting path
			message = scard.SCardGetErrorMessage(result)
			raise SelectPathError('Error selecting path: {0}'.format(message))

		return response

	def read_binary(self, offset, limit):
		"""Read binary data from card _after_ selecting path"""
		data = []

		limit = min(limit, 255)
		end_position = offset + limit
		current_position = offset

		# read data from card in small chunks
		while current_position < end_position:
			max_length = end_position - current_position

			if max_length > 0xFF:
				max_length = 0xFF

			# create request
			request = CardCommand.READ_BINARY[:]
			request.append(current_position >> 8)
			request.append(current_position & 0xFF)
			request.append(max_length)

			data.extend(self.get_data(request))
			current_position += max_length

		return data

	def read_file(self, card_file):
		"""Select and read file from card"""
		self.select_path(card_file)

		# get header
		header = self.read_binary(0, 6)
		file_size = (header[5] << 8) + header[4]

		# get data
		data = self.read_binary(6, file_size)

		return header, data

	def disconnect(self):
		"""Safely disconnect card"""
		result = scard.SCardDisconnect(self._handle, scard.SCARD_UNPOWER_CARD)

		if result != scard.SCARD_S_SUCCESS:
			# failed selecting path
			message = scard.SCardGetErrorMessage(result)
			raise DisconnectCardError('Error disconnecting card: {0}'.format(message))


class GemaltoCard(Card):
	CARD_AID = [
		0xF3, 0x81, 0x00, 0x00, 0x02, 0x53, 0x45,
		0x52, 0x49, 0x44, 0x01
	]

	def __init__(self, handle, protocol):
		self._handle = handle
		self._protocol = protocol

		command = [0x00, 0xA4, 0x04, 0x00]
		command.append(len(self.CARD_AID))
		command.extend(self.CARD_AID)
		command.append(0x00)
		scard.SCardTransmit(
			handle,
			protocol,
			command
		)

	def select_path(self, path, ne=4):
		"""Select path on card"""
		request = [0x00, 0xA4, 0x08, 0x00]
		request.append(len(path))
		request.extend(path)
		request.append(ne)

		# transmit command to card
		result, response = scard.SCardTransmit(
			self._handle,
			self._protocol,
			request
		)

		# raise error if needed
		if result != scard.SCARD_S_SUCCESS:
			# failed selecting path
			message = scard.SCardGetErrorMessage(result)
			raise SelectPathError('Error selecting path: {0}'.format(message))

		return response

	def read_file(self, card_file, strip_tag=False):
		"""Select and read file from card"""
		file_info = self.select_path(card_file, 4)

		length = (file_info[2] << 8) + file_info[3]
		offset = 0
		known_real_length = False

		output = []
		while length > 0:
			data = self.read_binary(offset, length)
			if not known_real_length:
				# get length from outher tag, skip first 4 bytes (outher tag + length)
				# if strip_tag is true, skip 4 more bytes (inner tag + length) and return content
				length = ((data[3])<<8) + (data[2]);
				skip = 8 if strip_tag else 4
				output = [char for char in data[skip:len(data)]]
				#output.append(data[skip:len(data)-skip]);
				known_real_length = True;
			else:
				output = [char for char in data[0: len(data)]]
				#output.append(data[0: len(data)]);

			offset += len(data)
			length -= len(data)

		return [], output