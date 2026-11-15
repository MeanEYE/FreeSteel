#
#		FreeSteel
#		Card Monitor
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

import time

from threading import Thread
from gi.repository import GLib

from freesteel.reader import Reader
from freesteel.eid_card import EidCard
from freesteel.exceptions import EmptyReaderListError, GetReaderListError, GetContextError
from freesteel.exceptions import SelectPathError, GetDataError


class CardMonitor:
	"""Watch reader for cards and report what was found to the interface"""

	RETRY_DELAY = 2  # seconds to wait before looking for reader again

	def __init__(self, handler):
		# object with methods which are called when something happens:
		#
		#	show_no_reader(), show_no_card(), show_reading(),
		#	show_card(data), show_error(message)
		self._handler = handler
		self._thread = None

	def __call_handler(self, method_name, arguments):
		"""Call method of handler, executed in main thread"""
		getattr(self._handler, method_name)(*arguments)

		# returning false prevents this from being called again
		return False

	def __notify(self, method_name, *arguments):
		"""Schedule call to handler's method"""
		# waiting for reader would freeze the window, so it is done in separate
		# thread. interface must not be touched from there, instead the call
		# is handed over to main loop which makes it when it has nothing to do
		GLib.idle_add(self.__call_handler, method_name, arguments)

	def __get_reader(self):
		"""Get first reader on the system"""
		try:
			names = Reader.get_list()

		except (GetReaderListError, GetContextError):
			# connection to smart card service was lost, forget
			# it so new one is made on the next attempt
			Reader.context = None
			raise

		return Reader(names[0], Reader.context)

	def __read_certificates(self, eid_card):
		"""Read certificates from card, empty list when there are none"""
		try:
			result = eid_card.get_certificates()

		except (NotImplementedError, SelectPathError, GetDataError):
			# older cards are not supported and some cards don't have
			# anything to do with certificates, rest of data is still shown
			result = []

		return result

	def __read_card(self, card):
		"""Read everything interface shows from card"""
		eid_card = EidCard(card)

		try:
			result = {
				'document': eid_card.get_document(),
				'personal': eid_card.get_personal(),
				'residence': eid_card.get_residence(),
				'photo': eid_card.get_photo(),
				'certificates': self.__read_certificates(eid_card)
			}

		finally:
			# data is copied, card is no longer needed
			card.disconnect()

		return result

	def __watch_reader(self):
		"""Wait for one card, report its data and wait for it to be removed"""
		reader = self.__get_reader()

		self.__notify('show_no_card')
		card = reader.wait_for_card()

		if card is None:
			# reader was disconnected while waiting
			return

		self.__notify('show_reading')
		self.__notify('show_card', self.__read_card(card))

	def __run(self):
		"""Watch reader until program exits, executed in separate thread"""
		while True:
			try:
				self.__watch_reader()

			except EmptyReaderListError:
				self.__notify('show_no_reader')
				time.sleep(self.RETRY_DELAY)
				continue

			except Exception as error:
				# nothing should stop the monitor, whatever went wrong
				# is shown and card has to be taken out to try again
				self.__notify('show_error', str(error))

			try:
				# keep what is shown until card is removed
				self.__get_reader().wait_for_card_removal()

			except Exception:
				# reader or service is gone, start over after short pause
				time.sleep(self.RETRY_DELAY)

	def start(self):
		"""Start watching reader"""
		# daemon thread doesn't keep program alive once window is closed
		self._thread = Thread(target=self.__run, daemon=True)
		self._thread.start()
