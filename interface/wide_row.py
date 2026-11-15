#
#		FreeSteel
#		Wide Row
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


class WideRow(Adw.PreferencesRow):
	"""Row showing several labeled values next to each other"""

	# sizes chosen to match regular rows
	MARGIN = (12, 8)  # horizontal and vertical space around content
	COLUMN_SPACING = 12
	LABEL_SPACING = 3

	def __init__(self, values):
		"""Create row from list of (label, value) pairs"""
		Adw.PreferencesRow.__init__(self)

		# row only shows data, there is nothing to activate
		self.set_activatable(False)

		# all columns are given the same width
		box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, self.COLUMN_SPACING)
		box.set_homogeneous(True)
		box.set_margin_start(self.MARGIN[0])
		box.set_margin_end(self.MARGIN[0])
		box.set_margin_top(self.MARGIN[1])
		box.set_margin_bottom(self.MARGIN[1])

		for label, value in values:
			# small label above value, the way regular rows look
			label_title = Gtk.Label.new(label)
			label_title.set_xalign(0)
			label_title.set_wrap(True)
			label_title.add_css_class('caption')
			label_title.add_css_class('dim-label')

			label_value = Gtk.Label.new(value)
			label_value.set_xalign(0)
			label_value.set_wrap(True)
			label_value.set_selectable(True)

			column = Gtk.Box.new(Gtk.Orientation.VERTICAL, self.LABEL_SPACING)
			column.set_valign(Gtk.Align.CENTER)
			column.append(label_title)
			column.append(label_value)

			box.append(column)

		self.set_child(box)
