# -*- coding: utf-8 -*-
#
# Picard, the next-generation MusicBrainz tagger
#
# Copyright (C) 2025 Laurent Monin
# Copyright (C) 2025 Philipp Wolfer
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

from PyQt6 import (
    QtCore,
    QtWidgets,
)

from picard.i18n import gettext as _

from picard.ui.dialogs.plugininfo import PluginInfoDialog
from picard.ui.util import font_scaled_size


class PluginDetailsWidget(QtWidgets.QWidget):
    """Widget for displaying plugin details."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Cache tagger instance for performance
        self.tagger = QtWidgets.QApplication.instance()
        self.plugin_manager = self.tagger.get_plugin_manager()

        self.setup_ui()
        self.current_plugin = None

    def setup_ui(self):
        """Setup the details widget."""
        # Set minimum width to prevent resizing when content changes
        self.setMinimumWidth(font_scaled_size(self, 30, 1).width())

        layout = QtWidgets.QVBoxLayout(self)

        # Plugin name
        self.name_label = QtWidgets.QLabel()
        font = self.name_label.font()
        font.setBold(True)
        font.setPointSizeF(font.pointSizeF() * 1.2)
        self.name_label.setFont(font)
        self.name_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.name_label)

        # Description
        self.description_label = QtWidgets.QLabel()
        self.description_label.setWordWrap(True)
        self.description_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.description_label)

        # Details grid
        details_widget = QtWidgets.QWidget()
        self.details_layout = QtWidgets.QFormLayout(details_widget)

        self.version_label = QtWidgets.QLabel()
        self.version_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.details_layout.addRow(_("Version:"), self.version_label)

        self.authors_label = QtWidgets.QLabel()
        self.authors_label.setWordWrap(True)
        self.authors_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.details_layout.addRow(_("Authors:"), self.authors_label)

        self.maintainers_label = QtWidgets.QLabel()
        self.maintainers_label.setWordWrap(True)
        self.maintainers_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.details_layout.addRow(_("Maintainers:"), self.maintainers_label)

        layout.addWidget(details_widget)

        # Action buttons
        button_layout = QtWidgets.QHBoxLayout()

        self.description_button = QtWidgets.QPushButton(_("Information"))
        self.description_button.clicked.connect(self._show_full_description)
        button_layout.addWidget(self.description_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        layout.addStretch()

        # Initially hide everything
        self.setVisible(False)

    def show_plugin(self, plugin, has_update=None):
        """Show details for the given plugin.

        Args:
            plugin: Plugin to show
            has_update: Unused (kept for API compatibility)
        """
        self.current_plugin = plugin

        if plugin is None:
            self.setVisible(False)
            return

        self.name_label.setText(plugin.name())

        # Get description from manifest
        description = _("No description available")
        if plugin.manifest and hasattr(plugin.manifest, 'description_i18n'):
            try:
                description = plugin.manifest.description_i18n() or description
            except Exception:
                pass
        self.description_label.setText(description)

        # Version
        version = ''
        if plugin.manifest and plugin.manifest.version:
            version = str(plugin.manifest.version)
        self.details_layout.setRowVisible(self.version_label, bool(version))
        if version:
            self.version_label.setText(version)

        # Authors
        authors = self._get_authors_display(plugin)
        self.details_layout.setRowVisible(self.authors_label, bool(authors))
        if authors:
            self.authors_label.setText(authors)

        # Maintainers
        maintainers = self._get_maintainers_display(plugin)
        self.details_layout.setRowVisible(self.maintainers_label, bool(maintainers))
        if maintainers:
            self.maintainers_label.setText(maintainers)

        # Always enable description button
        self.description_button.setEnabled(True)

        self.setVisible(True)

    def _show_full_description(self):
        """Show plugin information dialog."""
        if not self.current_plugin:
            return

        dialog = PluginInfoDialog(self.current_plugin, self)
        dialog.exec()

    def _get_authors_display(self, plugin):
        """Get authors display text."""
        if plugin.manifest and hasattr(plugin.manifest, 'authors'):
            authors = plugin.manifest.authors
            if authors:
                return ", ".join(authors)
        return ""

    def _get_maintainers_display(self, plugin):
        """Get maintainers display text."""
        if plugin.manifest and hasattr(plugin.manifest, 'maintainers'):
            maintainers = plugin.manifest.maintainers
            if maintainers:
                return ", ".join(maintainers)
        return ""
