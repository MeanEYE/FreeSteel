#
#		FreeSteel
#		Application
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

from gi.repository import Adw, Gio, Gtk

from interface.card_monitor import CardMonitor
from interface.main_window import MainWindow


class Application(Adw.Application):
	"""Application object, owns windows and keeps program running while they are open"""

	ID = 'org.freesteel.FreeSteel'  # unique name, also makes sure only one instance is running

	def __init__(self):
		Adw.Application.__init__(
			self,
			application_id=self.ID,
			flags=Gio.ApplicationFlags.DEFAULT_FLAGS
		)

		self._window = None
		self._monitor = None

		# icon is installed under the same name as application
		Gtk.Window.set_default_icon_name(self.ID)

		# connect signals
		self.connect('activate', self._handle_activate)

	def _handle_activate(self, application, data=None):
		"""Show main window when application is started"""
		# activation also happens when program is started for
		# the second time, in which case existing window is shown
		if self._window is None:
			self._window = MainWindow(self)

			# window is told about cards by monitor from now on
			self._monitor = CardMonitor(self._window)
			self._monitor.start()

		self._window.present()
