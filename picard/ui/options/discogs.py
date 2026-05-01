# -*- coding: utf-8 -*-
#
# Picard, the next-generation MusicBrainz tagger
#
# Copyright (C) 2026 Stephane Rossignol
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.


from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt

from picard.config import get_config
from picard.extension_points.options_pages import register_options_page
from picard.i18n import (
    N_,
    gettext as _,
)

from picard.ui.options import OptionsPage


class DiscogsOptionsPage(OptionsPage):
    NAME = 'discogs'
    TITLE = N_("Discogs")
    PARENT = 'advanced'
    SORT_ORDER = 25
    ACTIVE = True
    HELP_URL = ""

    OPTIONS = (
        ('discogs_enabled', ['discogs_enabled']),
        ('discogs_token', ['discogs_token']),
        ('discogs_match_threshold', ['discogs_match_threshold']),
    )

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        self.discogs_enabled = QtWidgets.QCheckBox(
            _("Use Discogs to improve album matching"))
        layout.addWidget(self.discogs_enabled)

        layout.addSpacing(10)

        token_group = QtWidgets.QGroupBox(_("Discogs API Token"))
        token_layout = QtWidgets.QVBoxLayout(token_group)

        desc = QtWidgets.QLabel(
            _("A personal access token is required to use the Discogs API "
              "(60 requests/min with token, 25 without)."))
        desc.setWordWrap(True)
        token_layout.addWidget(desc)

        token_row = QtWidgets.QHBoxLayout()
        token_row.addWidget(QtWidgets.QLabel(_("Token:")))
        self.discogs_token = QtWidgets.QLineEdit()
        self.discogs_token.setPlaceholderText(
            _("Paste your Discogs personal access token here"))
        token_row.addWidget(self.discogs_token)
        token_layout.addLayout(token_row)

        link = QtWidgets.QLabel(
            '<a href="https://www.discogs.com/settings/developers">'
            + _("Get your token on discogs.com/settings/developers")
            + '</a>')
        link.setOpenExternalLinks(True)
        link.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction)
        token_layout.addWidget(link)

        layout.addWidget(token_group)

        layout.addSpacing(10)

        threshold_group = QtWidgets.QGroupBox(_("Matching"))
        threshold_layout = QtWidgets.QHBoxLayout(threshold_group)
        threshold_layout.addWidget(QtWidgets.QLabel(
            _("Minimum match score (0.0 - 1.0):")))
        self.discogs_match_threshold = QtWidgets.QDoubleSpinBox()
        self.discogs_match_threshold.setRange(0.0, 1.0)
        self.discogs_match_threshold.setSingleStep(0.05)
        self.discogs_match_threshold.setDecimals(2)
        threshold_layout.addWidget(self.discogs_match_threshold)
        layout.addWidget(threshold_group)

        layout.addStretch()

    def load(self):
        config = get_config()
        self.discogs_enabled.setChecked(config.setting['discogs_enabled'])
        self.discogs_token.setText(config.setting['discogs_token'])
        self.discogs_match_threshold.setValue(
            config.setting['discogs_match_threshold'])

    def save(self):
        config = get_config()
        config.setting['discogs_enabled'] = self.discogs_enabled.isChecked()
        config.setting['discogs_token'] = self.discogs_token.text().strip()
        config.setting['discogs_match_threshold'] = \
            self.discogs_match_threshold.value()


register_options_page(DiscogsOptionsPage)
