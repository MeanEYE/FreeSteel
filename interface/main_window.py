#
#		FreeSteel
#		Main Window
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

from gi.repository import Adw, Gtk

from interface.card_page import CardPage
from interface.certificate_checker import CertificateChecker


class MainWindow(Adw.ApplicationWindow):
	"""Main window of the application"""

	TITLE = 'FreeSteel'
	DEFAULT_SIZE = (650, 700)

	def __init__(self, application):
		Adw.ApplicationWindow.__init__(self, application=application)

		self._card_page = None
		self._checker = CertificateChecker()

		# configure window
		self.set_title(self.TITLE)
		self.set_default_size(*self.DEFAULT_SIZE)

		# create user interface
		header_bar = Adw.HeaderBar.new()

		# stack shows one of its pages at a time, either
		# status when there is no data or data from card
		self._stack = Gtk.Stack.new()
		self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

		self._status_page = Adw.StatusPage.new()
		self._stack.add_named(self._status_page, 'status')

		# pack user interface, this type of window has no title bar
		# of its own so header bar is placed above content
		toolbar_view = Adw.ToolbarView.new()
		toolbar_view.add_top_bar(header_bar)
		toolbar_view.set_content(self._stack)

		self.set_content(toolbar_view)

		self.show_no_card()

	def __show_status(self, icon_name, title, description):
		"""Show status page in place of card data"""
		self._status_page.set_icon_name(icon_name)
		self._status_page.set_title(title)
		self._status_page.set_description(description)

		self._stack.set_visible_child_name('status')
		self.__remove_card_page()

	def __remove_card_page(self):
		"""Remove page with data of the previous card"""
		if self._card_page is not None:
			self._stack.remove(self._card_page)
			self._card_page = None

	def show_no_reader(self):
		"""Tell user there is no reader"""
		self.__show_status(
			'dialog-warning-symbolic',
			'No reader',
			'Connect smart card reader to computer.'
		)

	def show_no_card(self):
		"""Tell user to insert card"""
		self.__show_status(
			'auth-smartcard-symbolic',
			'No card',
			'Insert electronic ID card in reader.'
		)

	def show_reading(self):
		"""Tell user card is being read"""
		self.__show_status(
			'auth-smartcard-symbolic',
			'Reading card',
			'This takes a few seconds.'
		)

	def show_error(self, message):
		"""Tell user card could not be read"""
		self.__show_status(
			'dialog-error-symbolic',
			'Card could not be read',
			message
		)

	def show_card(self, data):
		"""Show data read from card"""
		# page is made anew for every card
		self.__remove_card_page()

		self._card_page = CardPage(data, self._checker)
		self._stack.add_named(self._card_page, 'card')
		self._stack.set_visible_child_name('card')
