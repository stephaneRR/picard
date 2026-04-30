# -*- coding: utf-8 -*-
#
# Picard, the next-generation MusicBrainz tagger
#
# Copyright (C) 2025 Laurent Monin, Philipp Wolfer
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

from datetime import datetime

from PyQt6 import (
    QtCore,
    QtWidgets,
)

from picard import log
from picard.config import get_config
from picard.extension_points.options_pages import register_options_page
from picard.i18n import (
    N_,
    gettext as _,
    ngettext,
)

from picard.ui.options import OptionsPage
from picard.ui.widgets.plugindetailswidget import PluginDetailsWidget
from picard.ui.widgets.pluginlistwidget import PluginListWidget


class Plugins3OptionsPage(OptionsPage):
    """Plugin management options page."""

    NAME = 'plugins'
    TITLE = N_('Plugins')
    PARENT = None
    SORT_ORDER = 70
    ACTIVE = True
    HELP_URL = "/config/options_plugins.html"

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        # Cache plugin manager for performance
        self.plugin_manager = self.tagger.get_plugin_manager()

        self.setup_ui()

    def setup_ui(self):
        """Setup the UI."""
        layout = QtWidgets.QVBoxLayout(self)

        # Check whether plugins are available
        available, unavailable_reason = self.tagger.get_plugins_available()
        if not available:
            no_plugins_box = QtWidgets.QFrame(self)
            no_plugins_box.setStyleSheet("QFrame { background-color: #ffc107; color: black }")
            no_plugins_box.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
            no_plugins_box_layout = QtWidgets.QVBoxLayout(no_plugins_box)
            no_plugins_label = QtWidgets.QLabel(
                _("Plugins unavailable: {reason}.").format(reason=unavailable_reason), parent=no_plugins_box
            )
            no_plugins_box_layout.addWidget(no_plugins_label)
            layout.addWidget(no_plugins_box)
            layout.addStretch()
            return

        # Toolbar
        toolbar_layout = QtWidgets.QHBoxLayout()

        # Search box
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText(_("Search plugins…"))
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._filter_plugins)
        toolbar_layout.addWidget(self.search_edit)

        toolbar_layout.addStretch()

        self.details_toggle_button = QtWidgets.QPushButton(_("Hide Details"))
        self.details_toggle_button.setCheckable(True)
        self.details_toggle_button.setChecked(True)  # Details visible by default
        self.details_toggle_button.setToolTip(_("Show/hide plugin details panel"))
        self.details_toggle_button.clicked.connect(self._toggle_details_panel)
        toolbar_layout.addWidget(self.details_toggle_button)

        layout.addLayout(toolbar_layout)

        # Main content - splitter with plugin list and details
        self.splitter = QtWidgets.QSplitter()
        self.splitter.setObjectName("plugin_splitter")

        # Plugin list
        self.plugin_list = PluginListWidget()
        self.plugin_list.plugin_selection_changed.connect(self._on_plugin_selected)
        # Connect plugin state changes to refresh options dialog
        self.plugin_list.plugin_state_changed.connect(self._on_plugin_state_changed)
        self.splitter.addWidget(self.plugin_list)

        # Plugin details
        self.plugin_details = PluginDetailsWidget()
        self.splitter.addWidget(self.plugin_details)

        # Set splitter proportions
        self.splitter.setSizes([300, 200])

        layout.addWidget(self.splitter, 1)  # Give most space to splitter

        # Status mini-log (shows last 3 messages)
        self.status_log = QtWidgets.QTextEdit()
        self.status_log.setMaximumHeight(60)  # About 3 lines
        self.status_log.setReadOnly(True)
        self.status_log.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.status_messages = []  # Keep track of last 3 messages
        layout.addWidget(self.status_log, 0)  # Minimal space for status

    def _show_status(self, message, clear_after_ms=None):
        """Add message to status log (keeps last 3 messages)."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"

        # Add to messages list and keep only last 3
        self.status_messages.append(formatted_message)
        if len(self.status_messages) > 3:
            self.status_messages.pop(0)

        # Update display
        self.status_log.setPlainText("\n".join(self.status_messages))
        # Scroll to bottom to show latest message
        self.status_log.verticalScrollBar().setValue(self.status_log.verticalScrollBar().maximum())
        QtWidgets.QApplication.processEvents()

    def load(self):
        if not self.plugin_manager:
            return

        # Load plugins from plugin manager.
        self._show_status(_("Loading plugins…"))
        try:
            self._filter_plugins()
            plugin_count = len(self.plugin_manager.plugins)
            self._show_status(
                ngettext(
                    "Loaded {plugin_count:,d} plugin",
                    "Loaded {plugin_count:,d} plugins",
                    plugin_count,
                ).format(plugin_count=plugin_count)
            )
            self._show_enabled_state()
            self._update_details_button_text()
        except Exception as e:
            log.debug("Error loading plugins", exc_info=True)
            self._show_status(_("Error loading plugins: {}").format(str(e)))

    def _show_enabled_state(self):
        """Show UI when plugin system is enabled."""
        self.search_edit.setEnabled(True)

    def _filter_plugins(self):
        """Filter plugins based on search text."""
        search_text = self.search_edit.text().lower()

        if not search_text:
            # Show all plugins
            filtered_plugins = self.plugin_manager.plugins
        else:
            # Filter plugins by name
            filtered_plugins = []
            for plugin in self.plugin_manager.plugins:
                if search_text in plugin.name().lower():
                    filtered_plugins.append(plugin)

        self.plugin_list.populate_plugins(filtered_plugins)
        self._update_details_button_text()

    def save(self):
        """Save is handled automatically by direct config updates."""
        pass

    def _toggle_details_panel(self):
        """Toggle visibility of the plugin details panel."""
        is_visible = self.plugin_details.isVisible()

        if not is_visible:
            # Showing details - ensure a plugin is selected
            selected_items = self.plugin_list.selectedItems()
            if not selected_items and self.plugin_list.topLevelItemCount() > 0:
                first_item = self.plugin_list.topLevelItem(0)
                self.plugin_list.setCurrentItem(first_item)

        self.plugin_details.setVisible(not is_visible)
        self._update_details_button_text()

    def _update_details_button_text(self):
        """Update the details button text based on panel visibility."""
        has_plugins = self.plugin_list.topLevelItemCount() > 0
        self.details_toggle_button.setEnabled(has_plugins)

        if self.plugin_details.isVisible():
            self.details_toggle_button.setText(_("Hide Details"))
            self.details_toggle_button.setChecked(True)
        else:
            self.details_toggle_button.setText(_("Show Details"))
            self.details_toggle_button.setChecked(False)

    def _on_plugin_selected(self, plugin):
        """Handle plugin selection."""
        self.plugin_details.show_plugin(plugin, has_update=False)
        self._update_details_button_text()

    def _on_plugin_state_changed(self, plugin, action):
        """Handle plugin state changes (enable/disable)."""
        log.debug("_on_plugin_state_changed called: plugin=%s, action=%s", plugin.plugin_id, action)
        self._show_status(_('Plugin "{name}" {action}').format(name=plugin.name(), action=action))

        # Refresh the options dialog to update plugin option pages
        if getattr(self, 'dialog', None):
            self.dialog.refresh_plugin_pages()

    def _cleanup_plugin_settings(self, plugin_id):
        """Clean up plugin settings when plugin is uninstalled."""
        config = get_config()

        # Remove from do_not_update list
        do_not_update = list(config.persist.get('plugins3_do_not_update', []))
        if plugin_id in do_not_update:
            do_not_update.remove(plugin_id)
            config.persist['plugins3_do_not_update'] = do_not_update


register_options_page(Plugins3OptionsPage)
