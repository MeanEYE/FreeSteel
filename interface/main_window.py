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

import cairo

from datetime import date
from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, Gtk

from freesteel.eid_card import DocumentField, PersonalField, ResidenceField
from interface.card_page import CardPage
from interface.certificate_checker import CertificateChecker


# layout of the page printed by official application, measured on
# its printout. all sizes are in millimetres from the edge of A4 paper
class LegacyLayout:
	FONT = 'Arial'
	TITLE_SIZE = 4.66
	TEXT_SIZE = 3.88
	NOTE_SIZE = 3.1

	# horizontal lines
	LEFT = 20.97
	RIGHT = 188.8
	THIN_LINE = 0.3
	THICK_LINE = 0.38
	DOUBLE_LINE_SPACING = 1.02

	TITLE_TOP = 21.04
	TITLE_LEFT = 24.26
	TITLE_HEIGHT = 10.36
	TITLE_BASELINE = 6.73

	PHOTO_TOP = 36.65
	PHOTO_WIDTH = 41.9
	PHOTO_BORDER = 0.17

	# table with data, long text continues in the next line
	TABLE_TOP = 97.58
	LABEL_LEFT = 23.75
	LABEL_WIDTH = 44.6
	VALUE_LEFT = 69.05
	VALUE_WIDTH = 117.0
	ROW_HEIGHT = 8.68
	ROW_BASELINE = 5.75
	LINE_HEIGHT = 4.36

	# following are measured from the end of table
	DATE_BASELINE = 6.91
	NOTE_TOP = 25.75
	NOTE_HEIGHT = 12.1
	NOTE_BASELINE = 5.61
	NOTE_LINE_HEIGHT = 3.47

	TITLE = 'ČITAČ ELEKTRONSKE LIČNE KARTE: ŠTAMPA PODATAKA'
	PERSONAL_TITLE = 'Podaci o građaninu'
	DOCUMENT_TITLE = 'Podaci o dokumentu'
	PRINT_DATE = 'Datum štampe: {0}'
	NOTE = (
		'U čipu lične karte, podaci o imenu i prezimenu imaoca lične karte '
		'ispisani su na nacionalnom pismu onako kako su ispisani na samom '
		'obrascu lične karte, dok su ostali podaci ispisani latiničkim pismom.'
	)


# layout of the page designed for this application, easier to read than
# the official one. all sizes are in millimetres from the edge of A4 paper
class Layout(LegacyLayout):
	FONT = 'Sans'

	# shades of gray, from black to white
	TEXT_SHADE = 0.1
	LABEL_SHADE = 0.45
	LINE_SHADE = 0.8

	LEFT = 20.0
	RIGHT = 190.0
	TOP = 20.0
	LINE = 0.25

	PHOTO_RADIUS = 2.0
	PHOTO_SPACING = 8.0

	# header, text next to photo
	CAPTION_SIZE = 2.8
	CAPTION_BASELINE = 2.6
	NAME_SIZE = 7.5
	NAME_TOP = 7.0
	NAME_BASELINE = 6.5
	NAME_LINE_HEIGHT = 9.0
	NAME_SPACING = 4.0

	# fields, small label with value below it
	VALUE_SIZE = 4.0
	LABEL_BASELINE = 2.6
	VALUE_BASELINE = 7.6
	VALUE_LINE_HEIGHT = 5.2
	CELL_HEIGHT = 12.5
	CELL_SPACING = 6.0

	# titled groups of fields
	SECTION_SIZE = 3.2
	SECTION_SPACING = 8.0
	SECTION_BASELINE = 3.0
	SECTION_LINE = 5.0
	SECTION_HEIGHT = 9.0

	FOOTER_TOP = 266.0
	FOOTER_BASELINE = 4.6
	FOOTER_LINE_HEIGHT = 3.6

	TITLE = 'ELEKTRONSKA LIČNA KARTA'
	RESIDENCE_TITLE = 'PREBIVALIŠTE'
	DOCUMENT_TITLE = 'DOKUMENT'
	PRINT_DATE = 'Štampano {0}'
	EMPTY_VALUE = '-'


class MainWindow(Adw.ApplicationWindow):
	"""Main window of the application"""

	TITLE = 'FreeSteel'
	DEFAULT_SIZE = (650, 700)
	ACTION_PRINT_LEGACY = 'print-legacy'

	def __init__(self, application):
		Adw.ApplicationWindow.__init__(self, application=application)

		self._card_page = None
		self._card = None
		self._checker = CertificateChecker()

		# configure window
		self.set_title(self.TITLE)
		self.set_default_size(*self.DEFAULT_SIZE)

		# create user interface
		header_bar = Adw.HeaderBar.new()

		# header buttons
		# clicking the button prints our layout, the official
		# one is offered in menu which drops down next to it
		action = Gio.SimpleAction.new(self.ACTION_PRINT_LEGACY, None)
		action.connect('activate', self.__handle_print_legacy)
		self.add_action(action)

		menu = Gio.Menu.new()
		menu.append('Print official layout', 'win.' + self.ACTION_PRINT_LEGACY)

		self._button_print = Adw.SplitButton.new()
		self._button_print.set_icon_name('document-print-symbolic')
		self._button_print.set_tooltip_text('Print document')
		self._button_print.set_dropdown_tooltip('More ways to print')
		self._button_print.set_menu_model(menu)
		self._button_print.connect('clicked', self.__handle_print_click)
		header_bar.pack_start(self._button_print)

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

	def __handle_print_click(self, button, data=None):
		"""Handle clicking on print button."""
		self.__print(self.__draw_page)

	def __handle_print_legacy(self, action, parameter, data=None):
		"""Handle choosing official layout from print menu."""
		self.__print(self.__draw_page_legacy)

	def __print(self, draw_page):
		"""Show print dialog and print card with specified method"""
		operation = Gtk.PrintOperation()
		operation.set_n_pages(1)
		operation.set_unit(Gtk.Unit.MM)
		operation.connect('draw-page', draw_page, self._card)
		operation.run(Gtk.PrintOperationAction.PRINT_DIALOG, self)

	def __draw_page(self, operation, context, page_nr, card):
		"""Render page for printing."""
		ctx = context.get_cairo_context()
		personal = card['personal']
		document = card['document']
		residence = card['residence']

		ctx.save()

		# positions are measured from the edge of paper, while
		# drawing normally starts inside of paper margins
		if not operation.props.use_full_page:
			setup = context.get_page_setup()
			ctx.translate(
				-setup.get_left_margin(Gtk.Unit.MM),
				-setup.get_top_margin(Gtk.Unit.MM)
			)

		# letters are otherwise moved to whole units, which spreads text
		options = cairo.FontOptions()
		options.set_hint_metrics(cairo.HINT_METRICS_OFF)
		ctx.set_font_options(options)

		# draw photo in top left corner, text of the header goes next to it
		top = Layout.TOP
		text_left = Layout.LEFT
		photo_bottom = top
		photo = self.__load_photo(card['photo'])

		if photo is not None:
			scale = Layout.PHOTO_WIDTH / photo.get_width()
			photo_height = photo.get_height() * scale

			# corners of the photo are rounded
			ctx.save()
			self.__add_rounded_rectangle(
				ctx,
				Layout.LEFT,
				top,
				Layout.PHOTO_WIDTH,
				photo_height,
				Layout.PHOTO_RADIUS
			)
			ctx.clip()
			ctx.translate(Layout.LEFT, top)
			ctx.scale(scale, scale)
			Gdk.cairo_set_source_pixbuf(ctx, photo, 0, 0)
			ctx.paint()
			ctx.restore()

			text_left += Layout.PHOTO_WIDTH + Layout.PHOTO_SPACING
			photo_bottom += photo_height

		# draw caption with date of printing on the opposite side
		today = Layout.PRINT_DATE.format(date.today().strftime('%d.%m.%Y.'))

		self.__set_text(ctx, Layout.CAPTION_SIZE, Layout.LABEL_SHADE)
		ctx.move_to(text_left, top + Layout.CAPTION_BASELINE)
		ctx.show_text(Layout.TITLE)
		ctx.move_to(
			Layout.RIGHT - ctx.text_extents(today).x_advance,
			top + Layout.CAPTION_BASELINE
		)
		ctx.show_text(today)

		# draw name, the most prominent text on the page
		name = '{0} {1}'.format(
			personal.get(PersonalField.FIRST_NAME, '').strip(),
			personal.get(PersonalField.LAST_NAME, '').strip()
		)

		self.__set_text(ctx, Layout.NAME_SIZE, Layout.TEXT_SHADE, True)
		top += Layout.NAME_TOP

		for line in self.__wrap_text(ctx, name, Layout.RIGHT - text_left):
			ctx.move_to(text_left, top + Layout.NAME_BASELINE)
			ctx.show_text(line)
			top += Layout.NAME_LINE_HEIGHT

		# draw the rest of personal data
		birth_place = (
			personal.get(PersonalField.BIRTH_PLACE, ''),
			personal.get(PersonalField.BIRTH_MUNICIPAL, ''),
			personal.get(PersonalField.BIRTH_COUNTRY, '')
		)
		rows = (
			(
				('Ime jednog roditelja', personal.get(PersonalField.PARENT_NAME, '')),
				('Pol', personal.get(PersonalField.SEX, ''))
			),
			(
				('Datum rođenja', self.__format_date(personal.get(PersonalField.DATE_OF_BIRTH, ''))),
				('JMBG', personal.get(PersonalField.PIN, ''))
			),
			(
				('Mesto rođenja, opština i država', self.__join_values(birth_place)),
			)
		)
		top = self.__draw_fields(
			ctx,
			text_left,
			top + Layout.NAME_SPACING,
			Layout.RIGHT - text_left,
			rows
		)

		# sections take whole width of the page, below photo
		top = max(top, photo_bottom)

		rows = (
			(
				('Adresa', self.__format_address(residence)),
			),
			(
				('Datum promene adrese', self.__format_date(residence.get(ResidenceField.ADDRESS_DATE, ''))),
			)
		)
		top = self.__draw_section(ctx, top, Layout.RESIDENCE_TITLE, rows)

		rows = (
			(
				('Broj dokumenta', document.get(DocumentField.ID, '')),
				('Dokument izdaje', document.get(DocumentField.ISSUER, ''))
			),
			(
				('Datum izdavanja', self.__format_date(document.get(DocumentField.RELEASE_DATE, ''))),
				('Važi do', self.__format_date(document.get(DocumentField.VALID_UNTIL, '')))
			)
		)
		top = self.__draw_section(ctx, top, Layout.DOCUMENT_TITLE, rows)

		# draw note about alphabets at the bottom of the page
		self.__draw_separator(ctx, Layout.FOOTER_TOP)
		self.__set_text(ctx, Layout.CAPTION_SIZE, Layout.LABEL_SHADE)
		lines = self.__wrap_text(ctx, Layout.NOTE, Layout.RIGHT - Layout.LEFT)

		for index, line in enumerate(lines):
			ctx.move_to(
				Layout.LEFT,
				Layout.FOOTER_TOP + Layout.FOOTER_BASELINE + index * Layout.FOOTER_LINE_HEIGHT
			)
			ctx.show_text(line)

		# restore context
		ctx.restore()

	def __set_text(self, ctx, size, shade, bold=False):
		"""Select size, shade of gray and weight for text which follows"""
		weight = cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL

		ctx.select_font_face(Layout.FONT, cairo.FONT_SLANT_NORMAL, weight)
		ctx.set_font_size(size)
		ctx.set_source_rgb(shade, shade, shade)

	def __add_rounded_rectangle(self, ctx, left, top, width, height, radius):
		"""Add rectangle with rounded corners to current path"""
		right = left + width
		bottom = top + height
		quarter = 3.141592653589793 / 2

		ctx.new_sub_path()
		ctx.arc(right - radius, top + radius, radius, -quarter, 0)
		ctx.arc(right - radius, bottom - radius, radius, 0, quarter)
		ctx.arc(left + radius, bottom - radius, radius, quarter, 2 * quarter)
		ctx.arc(left + radius, top + radius, radius, 2 * quarter, 3 * quarter)
		ctx.close_path()

	def __draw_separator(self, ctx, top):
		"""Draw light horizontal line across the page"""
		shade = Layout.LINE_SHADE

		ctx.set_source_rgb(shade, shade, shade)
		ctx.rectangle(
			Layout.LEFT,
			top,
			Layout.RIGHT - Layout.LEFT,
			Layout.LINE
		)
		ctx.fill()

	def __draw_section(self, ctx, top, title, rows):
		"""Draw titled group of fields and return position below it"""
		top += Layout.SECTION_SPACING

		self.__set_text(ctx, Layout.SECTION_SIZE, Layout.TEXT_SHADE, True)
		ctx.move_to(Layout.LEFT, top + Layout.SECTION_BASELINE)
		ctx.show_text(title)
		self.__draw_separator(ctx, top + Layout.SECTION_LINE)

		return self.__draw_fields(
			ctx,
			Layout.LEFT,
			top + Layout.SECTION_HEIGHT,
			Layout.RIGHT - Layout.LEFT,
			rows
		)

	def __draw_fields(self, ctx, left, top, width, rows):
		"""Draw rows of fields, small label above each value, and return position below them"""
		for row in rows:
			# fields missing on card are printed as well, marked as empty
			cells = [(label, value.strip() or Layout.EMPTY_VALUE) for label, value in row]

			# all rows are split in the same number of columns so values line up
			column_count = max(len(row) for row in rows)
			cell_width = (width + Layout.CELL_SPACING) / column_count
			line_count = 1

			for index, (label, value) in enumerate(cells):
				cell_left = left + index * cell_width

				# the last field can use the rest of the row
				columns = column_count - index if index == len(cells) - 1 else 1
				text_width = columns * cell_width - Layout.CELL_SPACING

				self.__set_text(ctx, Layout.CAPTION_SIZE, Layout.LABEL_SHADE)
				ctx.move_to(cell_left, top + Layout.LABEL_BASELINE)
				ctx.show_text(label)

				self.__set_text(ctx, Layout.VALUE_SIZE, Layout.TEXT_SHADE)
				lines = self.__wrap_text(ctx, value, text_width)

				for line_index, line in enumerate(lines):
					ctx.move_to(
						cell_left,
						top + Layout.VALUE_BASELINE + line_index * Layout.VALUE_LINE_HEIGHT
					)
					ctx.show_text(line)

				line_count = max(line_count, len(lines))

			# row grows with the longest of its values
			top += Layout.CELL_HEIGHT + (line_count - 1) * Layout.VALUE_LINE_HEIGHT

		return top

	def __draw_page_legacy(self, operation, context, page_nr, card):
		"""Render page the way official application prints it."""
		ctx = context.get_cairo_context()
		personal = card['personal']
		document = card['document']
		residence = card['residence']

		ctx.save()

		# positions are measured from the edge of paper, while
		# drawing normally starts inside of paper margins
		if not operation.props.use_full_page:
			setup = context.get_page_setup()
			ctx.translate(
				-setup.get_left_margin(Gtk.Unit.MM),
				-setup.get_top_margin(Gtk.Unit.MM)
			)

		ctx.set_source_rgb(0, 0, 0)
		ctx.select_font_face(LegacyLayout.FONT, 0, 0)

		# letters are otherwise moved to whole units, which spreads text
		options = cairo.FontOptions()
		options.set_hint_metrics(cairo.HINT_METRICS_OFF)
		ctx.set_font_options(options)

		# draw title
		self.__draw_line(ctx, LegacyLayout.TITLE_TOP, LegacyLayout.THIN_LINE)
		self.__draw_line(ctx, LegacyLayout.TITLE_TOP + LegacyLayout.TITLE_HEIGHT, LegacyLayout.THIN_LINE)

		ctx.set_font_size(LegacyLayout.TITLE_SIZE)
		ctx.move_to(LegacyLayout.TITLE_LEFT, LegacyLayout.TITLE_TOP + LegacyLayout.TITLE_BASELINE)
		ctx.show_text(LegacyLayout.TITLE)

		# draw photo
		photo = self.__load_photo(card['photo'])

		if photo is not None:
			scale = LegacyLayout.PHOTO_WIDTH / photo.get_width()

			ctx.save()
			ctx.translate(LegacyLayout.LEFT, LegacyLayout.PHOTO_TOP)
			ctx.scale(scale, scale)
			Gdk.cairo_set_source_pixbuf(ctx, photo, 0, 0)
			ctx.paint()
			ctx.restore()

			# photo has thin border around it
			ctx.set_line_width(LegacyLayout.PHOTO_BORDER)
			ctx.rectangle(
				LegacyLayout.LEFT,
				LegacyLayout.PHOTO_TOP,
				LegacyLayout.PHOTO_WIDTH,
				photo.get_height() * scale
			)
			ctx.stroke()

		# draw personal data
		ctx.set_font_size(LegacyLayout.TEXT_SIZE)
		top = LegacyLayout.TABLE_TOP

		birth_place = (
			personal.get(PersonalField.BIRTH_PLACE, ''),
			personal.get(PersonalField.BIRTH_MUNICIPAL, ''),
			personal.get(PersonalField.BIRTH_COUNTRY, '')
		)
		rows = (
			('Prezime:', personal.get(PersonalField.LAST_NAME, '')),
			('Ime:', personal.get(PersonalField.FIRST_NAME, '')),
			('Ime jednog roditelja:', personal.get(PersonalField.PARENT_NAME, '')),
			('Datum rođenja:', self.__format_date(personal.get(PersonalField.DATE_OF_BIRTH, ''))),
			('Mesto rođenja, opština i država:', self.__join_values(birth_place)),
			('Prebivalište:', self.__format_address(residence)),
			('Datum promene adrese:', self.__format_date(residence.get(ResidenceField.ADDRESS_DATE, ''))),
			('JMBG:', personal.get(PersonalField.PIN, '')),
			('Pol:', personal.get(PersonalField.SEX, ''))
		)
		top = self.__draw_table(ctx, top, LegacyLayout.PERSONAL_TITLE, rows)

		# draw document data
		rows = (
			('Dokument izdaje:', document.get(DocumentField.ISSUER, '')),
			('Broj dokumenta:', document.get(DocumentField.ID, '')),
			('Datum izdavanja:', self.__format_date(document.get(DocumentField.RELEASE_DATE, ''))),
			('Važi do:', self.__format_date(document.get(DocumentField.VALID_UNTIL, '')))
		)
		top = self.__draw_table(ctx, top, LegacyLayout.DOCUMENT_TITLE, rows)

		# table ends with double line
		self.__draw_line(ctx, top, LegacyLayout.THICK_LINE)
		self.__draw_line(ctx, top + LegacyLayout.DOUBLE_LINE_SPACING, LegacyLayout.THICK_LINE)

		# draw date of printing
		today = date.today().strftime('%d.%m.%Y.')
		ctx.move_to(LegacyLayout.LABEL_LEFT, top + LegacyLayout.DATE_BASELINE)
		ctx.show_text(LegacyLayout.PRINT_DATE.format(today))

		# draw note about alphabets
		note_top = top + LegacyLayout.NOTE_TOP
		self.__draw_line(ctx, note_top, LegacyLayout.THIN_LINE)
		self.__draw_line(ctx, note_top + LegacyLayout.NOTE_HEIGHT, LegacyLayout.THIN_LINE)

		ctx.set_font_size(LegacyLayout.NOTE_SIZE)
		lines = self.__wrap_text(ctx, LegacyLayout.NOTE, LegacyLayout.RIGHT - LegacyLayout.LEFT)

		for index, line in enumerate(lines):
			ctx.move_to(
				LegacyLayout.LEFT,
				note_top + LegacyLayout.NOTE_BASELINE + index * LegacyLayout.NOTE_LINE_HEIGHT
			)
			ctx.show_text(line)

		# restore context
		ctx.restore()

	def __draw_line(self, ctx, top, thickness):
		"""Draw horizontal line across legacy page"""
		ctx.rectangle(LegacyLayout.LEFT, top, LegacyLayout.RIGHT - LegacyLayout.LEFT, thickness)
		ctx.fill()

	def __draw_table(self, ctx, top, title, rows):
		"""Draw titled rows of legacy page and return position below them"""
		# title is placed between two lines
		self.__draw_line(ctx, top, LegacyLayout.THICK_LINE)
		ctx.move_to(LegacyLayout.LABEL_LEFT, top + LegacyLayout.ROW_BASELINE)
		ctx.show_text(title)
		top += LegacyLayout.ROW_HEIGHT
		self.__draw_line(ctx, top, LegacyLayout.THICK_LINE)

		for label, value in rows:
			columns = (
				(LegacyLayout.LABEL_LEFT, self.__wrap_text(ctx, label, LegacyLayout.LABEL_WIDTH)),
				(LegacyLayout.VALUE_LEFT, self.__wrap_text(ctx, value.strip(), LegacyLayout.VALUE_WIDTH))
			)

			for left, lines in columns:
				for index, line in enumerate(lines):
					ctx.move_to(left, top + LegacyLayout.ROW_BASELINE + index * LegacyLayout.LINE_HEIGHT)
					ctx.show_text(line)

			# row grows with the longest of its texts
			line_count = max(len(lines) for left, lines in columns)
			top += LegacyLayout.ROW_HEIGHT + (line_count - 1) * LegacyLayout.LINE_HEIGHT

		return top

	def __wrap_text(self, ctx, text, width):
		"""Split text into lines not wider than specified"""
		result = []
		line = ''

		for word in text.split():
			candidate = word if line == '' else line + ' ' + word

			if line != '' and ctx.text_extents(candidate).x_advance > width:
				result.append(line)
				line = word

			else:
				line = candidate

		result.append(line)

		return result

	def __join_values(self, values):
		"""Join values with comma, leaving out empty ones"""
		return ', '.join(value.strip() for value in values if value.strip() != '')

	def __format_date(self, value):
		"""Turn eight digits from card into day, month and year"""
		value = value.strip()

		if len(value) == 8 and value.isdigit():
			value = '{0}.{1}.{2}.'.format(value[0:2], value[2:4], value[4:8])

		return value

	def __format_address(self, residence):
		"""Format place of residence the way official application does"""
		entrance = residence.get(ResidenceField.ENTRANCE, '').strip()
		floor = residence.get(ResidenceField.FLOOR, '').strip()
		apartment = residence.get(ResidenceField.APARTMENT, '').strip()

		# street with house number and letter
		address = '{0} {1}{2}'.format(
			residence.get(ResidenceField.STREET, '').strip(),
			residence.get(ResidenceField.NUMBER, '').strip(),
			residence.get(ResidenceField.LETTER, '').strip()
		).strip()

		if entrance != '':
			address += ' ulaz {0}'.format(entrance)

		if floor != '':
			address += ', {0}. sprat'.format(floor)

		if apartment != '':
			# apartment directly follows house number unless there is something between
			separator = ', stan ' if entrance != '' or floor != '' else '/'
			address += separator + apartment

		return self.__join_values((
			residence.get(ResidenceField.PLACE, ''),
			residence.get(ResidenceField.MUNICIPAL, ''),
			address
		))

	def __load_photo(self, photo):
		"""Load photo for printing or None when it can't be shown"""
		loader = GdkPixbuf.PixbufLoader.new()

		try:
			loader.write(bytes(photo))
			loader.close()

		except GLib.Error:
			# data on card is not image we can show
			return None

		return loader.get_pixbuf()

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

		# there is nothing to print without card
		self._card = None
		self._button_print.set_sensitive(False)

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

		self._card = data
		self._button_print.set_sensitive(True)
		self._card_page = CardPage(data, self._checker)
		self._stack.add_named(self._card_page, 'card')
		self._stack.set_visible_child_name('card')
