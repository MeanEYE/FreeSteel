#
#		FreeSteel
#		Card Page
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

from gi.repository import Adw, Gdk, GLib, Gtk

from freesteel.eid_card import DocumentField, PersonalField, ResidenceField
from interface.certificate_group import CertificateGroup
from interface.wide_row import WideRow


# what is shown and in which order, as list of groups:
#
#	(title, key in data read from card, ((field, label), ...))
#
# fields which are missing or empty on card are left out. several fields
# can be grouped in additional brackets to be shown next to each other
# in a single row instead of each one taking its own
GROUPS = (
	('Personal data', 'personal', (
		(
			(PersonalField.FIRST_NAME, 'Given name'),
			(PersonalField.PARENT_NAME, 'Parent\'s given name'),
			(PersonalField.LAST_NAME, 'Surname')
		),
		(
			(PersonalField.PIN, 'Personal number'),
			(PersonalField.SEX, 'Sex'),
			(PersonalField.DATE_OF_BIRTH, 'Date of birth')
		),
		(
			(PersonalField.BIRTH_PLACE, 'Place of birth'),
			(PersonalField.BIRTH_MUNICIPAL, 'Municipality of birth'),
			(PersonalField.BIRTH_COUNTRY, 'Country of birth')
		),
		(PersonalField.NATIONALITY, 'Nationality'),
		(PersonalField.PURPOSE_OF_STAY, 'Purpose of stay'),
		(PersonalField.PURPOSE_OF_STAY_OLD, 'Purpose of stay'),
		(PersonalField.NOTE, 'Note')
	)),
	('Document', 'document', (
		(
			(DocumentField.ID, 'Registration number'),
			(DocumentField.SERIAL_NUMBER, 'Serial number')
		),
		(
			(DocumentField.RELEASE_DATE, 'Date of issue'),
			(DocumentField.VALID_UNTIL, 'Valid until')
		),
		(
			(DocumentField.ISSUER, 'Issued by'),
			(DocumentField.ISSUER_COUNTRY, 'Issuing country')
		),
		(
			(DocumentField.NAME, 'Document'),
			(DocumentField.CHIP_SERIAL_NUMBER, 'Chip serial number')
		)
	)),
	('Residence', 'residence', (
		(
			(ResidenceField.STREET, 'Street'),
			(ResidenceField.NUMBER, 'House number')
		),
		(
			(ResidenceField.LETTER, 'House letter'),
			(ResidenceField.ENTRANCE, 'Entrance'),
			(ResidenceField.FLOOR, 'Floor'),
			(ResidenceField.APARTMENT, 'Apartment')
		),
		(
			(ResidenceField.PLACE, 'Place'),
			(ResidenceField.MUNICIPAL, 'Municipality')
		),
		(
			(ResidenceField.COUNTRY_CODE, 'Country'),
		),
		(
			(ResidenceField.ADDRESS_DATE, 'Registered on'),
			(ResidenceField.ADDRESS_LABEL, 'Type of residence')
		)
	))
)

# fields holding dates, stored on card as eight digits without separators
DATE_FIELDS = (
	PersonalField.DATE_OF_BIRTH,
	DocumentField.RELEASE_DATE,
	DocumentField.VALID_UNTIL,
	ResidenceField.ADDRESS_DATE
)


class CardPage(Adw.PreferencesPage):
	"""Page showing data read from one card"""

	def __init__(self, data, checker):
		Adw.PreferencesPage.__init__(self)

		self._checker = checker
		self._certificate_groups = []

		# create user interface
		photo = self.__create_photo(data['photo'])
		if photo is not None:
			group = Adw.PreferencesGroup.new()
			group.add(photo)
			self.add(group)

		for title, key, fields in GROUPS:
			group = self.__create_group(title, data[key], fields)

			# don't show title with nothing under it
			if group is not None:
				self.add(group)

		# every certificate gets a group of its own
		for certificate in data['certificates']:
			group = CertificateGroup(certificate, self._checker)
			self._certificate_groups.append(group)
			self.add(group)

		# certificates are issued on request, card doesn't have to have any
		if len(data['certificates']) == 0:
			row = Adw.ActionRow.new()
			row.set_title('No certificates were found on card')

			group = Adw.PreferencesGroup.new()
			group.set_title('Certificates')
			group.add(row)
			self.add(group)

	def __format_value(self, field, value):
		"""Prepare value from card for showing"""
		value = value.strip()

		# turn day, month and year into commonly used form
		if field in DATE_FIELDS and len(value) == 8 and value.isdigit():
			value = '{0}.{1}.{2}.'.format(value[0:2], value[2:4], value[4:8])

		return value

	def __create_photo(self, photo):
		"""Create widget showing photo or None when it can't be shown"""
		try:
			texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(photo))

		except GLib.Error:
			# data on card is not image we can show
			return None

		result = Gtk.Picture.new_for_paintable(texture)
		result.set_halign(Gtk.Align.CENTER)
		result.set_can_shrink(False)

		# round the corners like on other elements of the page
		result.add_css_class('card')
		result.set_overflow(Gtk.Overflow.HIDDEN)

		return result

	def __create_group(self, title, values, fields):
		"""Create group of rows or None when card has none of the fields"""
		result = Adw.PreferencesGroup.new()
		result.set_title(title)
		empty = True

		for entry in fields:
			# entry is either one field or several of them sharing a row
			if isinstance(entry[0], tuple):
				row = self.__create_wide_row(values, entry)

			else:
				row = self.__create_row(values, *entry)

			if row is not None:
				result.add(row)
				empty = False

		return None if empty else result

	def __create_row(self, values, field, label):
		"""Create row showing one field or None when card doesn't have it"""
		value = self.__format_value(field, values.get(field, ''))
		if value == '':
			return None

		result = Adw.ActionRow.new()

		# text comes from card and must not be treated as formatting
		result.set_use_markup(False)
		result.set_title(label)
		result.set_subtitle(value)
		result.set_subtitle_selectable(True)

		# this style makes label small and value prominent
		result.add_css_class('property')

		return result

	def __create_wide_row(self, values, fields):
		"""Create row showing fields next to each other or None when card has none of them"""
		pairs = []

		for field, label in fields:
			value = self.__format_value(field, values.get(field, ''))

			if value != '':
				pairs.append((label, value))

		return WideRow(pairs) if len(pairs) > 0 else None
