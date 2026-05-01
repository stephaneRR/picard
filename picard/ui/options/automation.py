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

from picard.config import get_config
from picard.extension_points.options_pages import register_options_page
from picard.i18n import (
    N_,
    gettext as _,
)

from picard.ui.options import OptionsPage


class AutomationOptionsPage(OptionsPage):
    NAME = 'automation'
    TITLE = N_("Automation")
    PARENT = 'advanced'
    SORT_ORDER = 20
    ACTIVE = True
    HELP_URL = ""

    OPTIONS = (
        ('auto_save_perfect_albums', ['auto_save_perfect_albums']),
        ('auto_remove_saved_albums', ['auto_remove_saved_albums']),
    )

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        save_group = QtWidgets.QGroupBox(_("Auto-save"))
        save_layout = QtWidgets.QVBoxLayout(save_group)

        self.auto_save_perfect_albums = QtWidgets.QCheckBox(
            _("Automatically save albums when all tracks are matched and cover art is loaded"))
        save_layout.addWidget(self.auto_save_perfect_albums)

        self.auto_remove_saved_albums = QtWidgets.QCheckBox(
            _("Remove albums from the list after auto-save completes"))
        save_layout.addWidget(self.auto_remove_saved_albums)

        save_desc = QtWidgets.QLabel(
            _("When auto-save is enabled, albums with a gold+star icon will be "
              "saved automatically after a 2-second delay. Files are tagged, "
              "renamed, and moved according to your file naming settings. "
              "If removal is enabled, the album disappears from the list once "
              "all files are saved successfully."))
        save_desc.setWordWrap(True)
        save_desc.setStyleSheet("color: gray; font-size: 11px;")
        save_layout.addWidget(save_desc)

        layout.addWidget(save_group)
        layout.addStretch()

        self.auto_save_perfect_albums.toggled.connect(
            self.auto_remove_saved_albums.setEnabled)
        self.auto_remove_saved_albums.setEnabled(False)

    def load(self):
        config = get_config()
        self.auto_save_perfect_albums.setChecked(
            config.setting['auto_save_perfect_albums'])
        self.auto_remove_saved_albums.setChecked(
            config.setting['auto_remove_saved_albums'])
        self.auto_remove_saved_albums.setEnabled(
            config.setting['auto_save_perfect_albums'])

    def save(self):
        config = get_config()
        config.setting['auto_save_perfect_albums'] = \
            self.auto_save_perfect_albums.isChecked()
        config.setting['auto_remove_saved_albums'] = \
            self.auto_remove_saved_albums.isChecked()


register_options_page(AutomationOptionsPage)
