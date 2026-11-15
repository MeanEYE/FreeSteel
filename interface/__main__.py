#
#		FreeSteel
#		Graphical Interface
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

import sys

try:
	# check if required libraries are available
	import gi

	gi.require_version('Gtk', '4.0')
	gi.require_version('Adw', '1')

except ValueError:
	# print error and die
	print('Error starting FreeSteel, missing GTK 4 or libadwaita')
	sys.exit(1)

else:
	# versions have to be selected before anything is imported from gi
	from interface.application import Application

	application = Application()
	sys.exit(application.run(sys.argv))
