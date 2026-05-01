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
        ('delete_junk_files', ['delete_junk_files']),
        ('delete_junk_files_pattern', ['delete_junk_files_pattern']),
    )

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Auto-save section
        save_group = QtWidgets.QGroupBox(_("Auto-save"))
        save_layout = QtWidgets.QVBoxLayout(save_group)

        self.auto_save_perfect_albums = QtWidgets.QCheckBox(
            _("Automatically save albums when all tracks are matched and cover art is loaded"))
        save_layout.addWidget(self.auto_save_perfect_albums)

        save_desc = QtWidgets.QLabel(
            _("When enabled, albums with a gold+star icon will be saved "
              "automatically after a 2-second delay. Files are tagged, "
              "renamed, and moved according to your file naming settings."))
        save_desc.setWordWrap(True)
        save_desc.setStyleSheet("color: gray; font-size: 11px;")
        save_layout.addWidget(save_desc)

        layout.addWidget(save_group)

        layout.addSpacing(10)

        # Junk files section
        junk_group = QtWidgets.QGroupBox(_("Junk file cleanup"))
        junk_layout = QtWidgets.QVBoxLayout(junk_group)

        self.delete_junk_files = QtWidgets.QCheckBox(
            _("Delete junk files when saving (moved to trash)"))
        junk_layout.addWidget(self.delete_junk_files)

        pattern_row = QtWidgets.QHBoxLayout()
        pattern_row.addWidget(QtWidgets.QLabel(_("File patterns:")))
        self.delete_junk_files_pattern = QtWidgets.QLineEdit()
        self.delete_junk_files_pattern.setPlaceholderText("*.url *.nfo *.m3u *.txt *.log")
        pattern_row.addWidget(self.delete_junk_files_pattern)
        junk_layout.addLayout(pattern_row)

        junk_desc = QtWidgets.QLabel(
            _("Files matching these patterns will be sent to the trash "
              "when saving an album. Uses wildcards (e.g. *.nfo *.txt). "
              "Files loaded in Picard are never deleted."))
        junk_desc.setWordWrap(True)
        junk_desc.setStyleSheet("color: gray; font-size: 11px;")
        junk_layout.addWidget(junk_desc)

        layout.addWidget(junk_group)

        layout.addStretch()

        # Wire enable/disable
        self.delete_junk_files.toggled.connect(
            self.delete_junk_files_pattern.setEnabled)
        self.delete_junk_files_pattern.setEnabled(False)

    def load(self):
        config = get_config()
        self.auto_save_perfect_albums.setChecked(
            config.setting['auto_save_perfect_albums'])
        self.delete_junk_files.setChecked(
            config.setting['delete_junk_files'])
        self.delete_junk_files_pattern.setText(
            config.setting['delete_junk_files_pattern'])
        self.delete_junk_files_pattern.setEnabled(
            config.setting['delete_junk_files'])

    def save(self):
        config = get_config()
        config.setting['auto_save_perfect_albums'] = \
            self.auto_save_perfect_albums.isChecked()
        config.setting['delete_junk_files'] = \
            self.delete_junk_files.isChecked()
        config.setting['delete_junk_files_pattern'] = \
            self.delete_junk_files_pattern.text().strip()


register_options_page(AutomationOptionsPage)
