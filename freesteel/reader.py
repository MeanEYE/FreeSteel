#
#		FreeSteel
#		Card Reader Implementation
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

from card import Card
from threading import Thread
from exceptions import GetContextError, ReleaseContextError, GetReaderListError
from exceptions import ConnectCardError, GetReaderStatusError, EmptyReaderListError


class Reader:
	"""Wrapper class for smart card reader"""

	context = None

	def __init__(self, name, context=None):
		# hidden fields
		self.__connected = False
		self.__hcard = None

		# public fields
		self.name = name
		self.protocol = scard.SCARD_PROTOCOL_T0 | scard.SCARD_PROTOCOL_T1
		self.active_protocol = None

		if context is None:
			# get default context
			self.context = self.get_context()

		else:
			# use user predefined context
			self.context = context

	def __get_card(self, protocol):
		"""Get card interface"""
		card = None

		# try connecting reader
		result, self.__hcard, self.active_protocol = scard.SCardConnect(
															self.context,
															self.name,
															scard.SCARD_SHARE_SHARED,
															self.protocol
														)
		if result != scard.SCARD_S_SUCCESS:
			# failed connecting reader
			message = scard.SCardGetErrorMessage(result)
			raise ConnectCardError('Error connecting to card: {0}'.format(message))

		else:
			# create card class and return it
			card = Card(self.__hcard, self.active_protocol)

		return card

	def __wait_for_reader_status(self, current_status, accepted_status):
		"""Wait for a specific reader status"""
		state = current_status

		# wait for new status
		while not state[0][1] & accepted_status:
			result, state = scard.SCardGetStatusChange(self.context, scard.INFINITE, state)

			if result != scard.SCARD_S_SUCCESS:
				# error getting reader status
				message = scard.SCardGetErrorMessage(result)
				raise GetReaderStatusError('Error getting reader state: {0}'.format(message))

			if state[0][1] & scard.SCARD_STATE_UNAVAILABLE:
				# exit loop when reader becomes unavailable
				break

		return state[0][1]

	@classmethod
	def get_context(class_):
		"""Get default context"""
		result, context = scard.SCardEstablishContext(scard.SCARD_SCOPE_USER)

		if result != scard.SCARD_S_SUCCESS:
			# failed to get context
			message = scard.SCardGetErrorMessage(result)
			raise GetContextError('Failed to establish context: {0}'.format(message))

		return context

	@classmethod
	def release_context(class_):
		"""Release context"""
		result = scard.SCardReleaseContext(class_.context)

		if result != scard.SCARD_S_SUCCESS:
			# failed to get context
			message = scard.SCardGetErrorMessage(result)
			raise ReleaseContextError('Failed to release context: {0}'.format(message))

	@classmethod
	def get_list(class_):
		"""Get reader list"""
		if class_.context is None:
			class_.context = class_.get_context()

		# get list of readers
		result, readers = scard.SCardListReaders(class_.get_context(), [])

		if result != scard.SCARD_S_SUCCESS:
			# failed to get reader list
			message = scard.SCardGetErrorMessage(result)
			raise GetReaderListError('Failed to obtain reader list: {0}'.format(message))

		elif len(readers) == 0:
			# no readers detected on the system
			raise EmptyReaderListError('No smart card readers detected!')

		return readers

	def wait_for_card(self, protocol=None, callback=None):
		"""Wait for card to be inserted"""
		card = None

		# set protocol if specified
		if protocol is not None:
			self.protocol = protocol

		# get reader status
		current_state = [(self.name, scard.SCARD_STATE_UNAWARE)]
		result, state = scard.SCardGetStatusChange(self.context, 0, current_state)

		if result != scard.SCARD_S_SUCCESS:
			# error getting reader status
			message = scard.SCardGetErrorMessage(result)
			raise GetReaderStatusError('Error getting reader state: {0}'.format(message))

		if state[0][1] & scard.SCARD_STATE_EMPTY:
			# reader is empty, wait for card insertion
			result = self.__wait_for_reader_status(state, scard.SCARD_STATE_PRESENT)

			# make sure reader wasn't disconnected
			if not result & scard.SCARD_STATE_UNAVAILABLE:
				card = self.__get_card(self.protocol)

		else:
			# card is already present in reader
			card = self.__get_card(self.protocol)

		# if callback is specified
		if callback is not None:
			callback(self, card)

		return card

	def wait_for_card_async(self, callback, protocol=None):
		"""Wait for card to be inserted asynchronously

		Callback method needs to accept two parameters.

			def callback(reader, card):
				pass

		"""
		arguments = {
					'protocol': protocol,
					'callback': callback
				}

		thread = Thread(target=self.wait_for_card, kwargs=arguments)
		thread.start()
