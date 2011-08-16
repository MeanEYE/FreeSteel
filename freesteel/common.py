#
#		FreeSteel
#		Commonly Used Functions
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

from reader import Reader


def get_reader_list():
	"""Get list of available readers"""
	return Reader.get_list()

def get_default_reader():
	"""Get default reader"""
	result = None
	readers = get_reader_list()

	if len(readers) > 0:
		result = Reader(readers[0])

	return result
