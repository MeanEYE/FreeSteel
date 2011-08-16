#
#		FreeSteel
#		Exception Definitions
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

class GetContextError(Exception): pass
class ReleaseContextError(Exception): pass

class GetReaderListError(Exception): pass
class EmptyReaderListError(Exception): pass
class GetReaderStatusError(Exception): pass

class GetDataError(Exception): pass
class SelectPathError(Exception): pass
class ConnectCardError(Exception): pass
class DisconnectCardError(Exception): pass
