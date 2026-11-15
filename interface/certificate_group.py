#
#		FreeSteel
#		Certificate Group
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
from cryptography import x509
from cryptography.x509.oid import ExtensionOID, NameOID

from freesteel.verification import load_certificate
from freesteel.exceptions import VerificationError
from interface.certificate_checker import CheckStatus
from interface.wide_row import WideRow


class CertificateGroup(Adw.PreferencesGroup):
	"""Group showing one certificate, made of row with information and row with controls"""

	DATE_FORMAT = '%d.%m.%Y.'
	TREE_INDENT = 24  # space added in front of certificate for each level of tree

	# label and its style shown for each status
	STATUS_LABELS = {
		CheckStatus.VERIFYING: ('Verifying', 'dim-label'),
		CheckStatus.TRUSTED: ('Verified', None),
		CheckStatus.CHECKING_REVOCATION: ('Verifying', 'dim-label'),
		CheckStatus.VALID: ('Verified', 'success'),
		CheckStatus.UNCHECKED: ('Verified', 'warning'),
		CheckStatus.INVALID: ('Unverified', 'error')
	}

	# statuses in which check is running
	BUSY_STATUSES = (CheckStatus.VERIFYING, CheckStatus.CHECKING_REVOCATION)

	# statuses in which user can ask for revocation to be checked
	REVOCATION_STATUSES = (CheckStatus.TRUSTED, CheckStatus.UNCHECKED)

	def __init__(self, data, checker):
		Adw.PreferencesGroup.__init__(self)

		self._data = data
		self._checker = checker
		self._tree_rows = []

		try:
			certificate = load_certificate(data)

		except VerificationError as error:
			# there is nothing to show or verify, only say what is wrong
			row = Adw.ActionRow.new()
			row.set_use_markup(False)
			row.set_title(str(error))

			self.set_title('Unreadable certificate')
			self.add(row)
			return

		self.set_title(self.__get_purpose(certificate))

		# create row with information
		self.add(WideRow((
			('Issued to', self.__get_common_name(certificate.subject)),
			('Valid', self.__get_validity(certificate))
		)))

		# create row with controls, which expands to show certificate tree
		self._controls_row = Adw.ExpanderRow.new()
		self._controls_row.set_title('Verification')

		# messages contain text from certificate which must not be treated as formatting
		self._controls_row.set_use_markup(False)

		# create status indicator
		self._spinner = Gtk.Spinner.new()
		self._label = Gtk.Label.new()

		# create button, revocation is checked only when user asks for
		# it since that is the only check which needs to download anything
		self._button = Gtk.Button.new_with_label('Check revocation')
		self._button.set_valign(Gtk.Align.CENTER)
		self._button.set_tooltip_text(
			'Downloads list of revoked certificates from the issuer. '
			'List is big and this can take several minutes.'
		)
		self._button.connect('clicked', self._handle_check_revocation)

		# suffixes are shown in order opposite to the one they are added
		# in, so this puts button first and status at the end of row
		self._controls_row.add_suffix(self._label)
		self._controls_row.add_suffix(self._spinner)
		self._controls_row.add_suffix(self._button)

		self.add(self._controls_row)

		# verify chain right away, result arrives through set_status
		self.set_status(CheckStatus.VERIFYING, 'Verifying chain')
		self._checker.check_chain(self._data, self.set_status)

	def __get_common_name(self, name):
		"""Get short name of person or authority"""
		attributes = name.get_attributes_for_oid(NameOID.COMMON_NAME)
		return attributes[0].value if len(attributes) > 0 else name.rfc4514_string()

	def __get_validity(self, certificate):
		"""Get period in which certificate is valid"""
		return '{0} \u2013 {1}'.format(
			certificate.not_valid_before_utc.strftime(self.DATE_FORMAT),
			certificate.not_valid_after_utc.strftime(self.DATE_FORMAT)
		)

	def __get_purpose(self, certificate):
		"""Get what certificate is used for"""
		try:
			usage = certificate.extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE).value

		except x509.ExtensionNotFound:
			return 'Certificate'

		# signatures made with this kind can't be denied later,
		# which is what makes them equal to handwritten ones
		if usage.content_commitment:
			return 'Certificate for qualified signature'

		return 'Certificate for authentication'

	def __show_tree(self, chain):
		"""Show certificates of chain as tree under row with controls"""
		# tree is shown as soon as it is known, after
		# that it stays the way user has left it
		was_expanded = self._controls_row.get_expanded() or len(self._tree_rows) == 0

		for row in self._tree_rows:
			self._controls_row.remove(row)

		self._tree_rows = []

		# chain starts with our certificate and ends with trusted one,
		# tree is shown the other way around with trusted one as its root
		for level, data in enumerate(reversed(chain)):
			certificate = load_certificate(data)

			if level == 0:
				role = 'Trusted authority'

			elif level == len(chain) - 1:
				role = 'Certificate from card'

			else:
				role = 'Authority'

			description = '{0}, valid {1}, serial number {2:X}'.format(
				role,
				self.__get_validity(certificate),
				certificate.serial_number
			)

			row = Adw.ActionRow.new()
			row.set_use_markup(False)
			row.set_title(self.__get_common_name(certificate.subject))
			row.set_subtitle(description)
			row.set_subtitle_selectable(True)

			# each level is moved further from the edge than the one above it
			if level > 0:
				indent = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
				indent.set_size_request(self.TREE_INDENT * (level - 1), -1)

				arrow = Gtk.Image.new_from_icon_name('go-next-symbolic')
				arrow.add_css_class('dim-label')

				# prefixes are shown in order opposite to the one they are added in
				row.add_prefix(arrow)
				row.add_prefix(indent)

			self._controls_row.add_row(row)
			self._tree_rows.append(row)

		# there is nothing to expand until tree is known
		self._controls_row.set_enable_expansion(len(self._tree_rows) > 0)
		self._controls_row.set_expanded(was_expanded and len(self._tree_rows) > 0)

	def _handle_check_revocation(self, widget, data=None):
		"""Start checking if certificate was revoked"""
		self._checker.check_revocation(self._data, self.set_status)

	def set_status(self, status, message, chain=None):
		"""Show result or progress of verification"""
		text, style = self.STATUS_LABELS[status]
		busy = status in self.BUSY_STATUSES

		# short answer goes in label, explanation under the title
		self._label.set_text(text)
		self._controls_row.set_subtitle(message)

		self._spinner.set_visible(busy)
		self._spinner.set_spinning(busy)
		self._button.set_visible(status in self.REVOCATION_STATUSES)

		# replace style of the previous status
		for _, other_style in self.STATUS_LABELS.values():
			if other_style is not None:
				self._label.remove_css_class(other_style)

		if style is not None:
			self._label.add_css_class(style)

		# tree is known once chain was built, show it from then on
		if chain is not None or len(self._tree_rows) == 0:
			self.__show_tree(chain or [])
