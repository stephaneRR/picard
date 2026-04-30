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
    QtGui,
    QtWidgets,
)

from picard import log
from picard.config import get_config
from picard.i18n import gettext as _
from picard.metadata import (
    album_metadata_processors,
    track_metadata_processors,
)
from picard.plugin3.plugin import PluginState
from picard.util import temporary_disconnect

from picard.ui.dialogs.plugin_order_selector import display_plugin_order_selector
from picard.ui.dialogs.plugininfo import PluginInfoDialog


# Column positions
COLUMN_ENABLED = 0
COLUMN_PLUGIN = 1
COLUMN_VERSION = 2


class PluginListWidget(QtWidgets.QWidget):
    """Widget for displaying and managing plugins."""

    plugin_selection_changed = QtCore.pyqtSignal(object)  # Emits selected plugin or None
    plugin_state_changed = QtCore.pyqtSignal(object, str)  # Emits plugin and action

    def __init__(self, parent=None):
        super().__init__(parent)
        self._toggling_plugins = set()  # Track plugins being toggled
        self._failed_enables = set()  # Track plugins that failed to enable
        self.setup_ui()

    def setup_ui(self):
        """Setup the widget layout."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create tree widget
        self.tree_widget = QtWidgets.QTreeWidget()
        self.tree_widget.setHeaderLabels([_("Enabled"), _("Plugin"), _("Version")])
        self.tree_widget.setRootIsDecorated(False)
        self.tree_widget.setAlternatingRowColors(True)
        self.tree_widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.tree_widget.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree_widget.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)

        # Set column sizing
        header = self.tree_widget.header()
        header.setSectionResizeMode(COLUMN_ENABLED, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COLUMN_PLUGIN, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COLUMN_VERSION, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(False)

        layout.addWidget(self.tree_widget)

        # Connect tree widget signals
        self.tree_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree_widget.itemClicked.connect(self._on_item_clicked)
        self.tree_widget.customContextMenuRequested.connect(self._show_context_menu)

        # Cache tagger instance for performance
        self.tagger = QtCore.QCoreApplication.instance()
        self.plugin_manager = self.tagger.get_plugin_manager()
        if not self.plugin_manager:
            raise RuntimeError("Plugin manager not available")

        # Guard to prevent double refresh during operations
        self._refreshing = False

    def populate_plugins(self, plugins):
        """Populate the widget with plugins."""
        self.tree_widget.clear()

        for plugin in sorted(plugins):
            item = QtWidgets.QTreeWidgetItem()

            # Column 0: Checkbox only (no text), centered
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                COLUMN_ENABLED,
                QtCore.Qt.CheckState.Checked if self._is_plugin_enabled(plugin) else QtCore.Qt.CheckState.Unchecked,
            )
            item.setTextAlignment(COLUMN_ENABLED, QtCore.Qt.AlignmentFlag.AlignCenter)

            # Column 1: Plugin name
            item.setText(COLUMN_PLUGIN, plugin.name())

            # Add tooltip with description if available
            try:
                description = plugin.manifest.description_i18n()
                if description:
                    item.setToolTip(COLUMN_PLUGIN, description)
            except (AttributeError, Exception):
                pass

            # Column 2: Version
            version = ''
            if plugin.manifest and plugin.manifest.version:
                version = str(plugin.manifest.version)
            item.setText(COLUMN_VERSION, version)

            # Store plugin reference
            item.setData(COLUMN_ENABLED, QtCore.Qt.ItemDataRole.UserRole, plugin)

            self.tree_widget.addTopLevelItem(item)

    def _is_plugin_enabled(self, plugin):
        """Check if plugin is enabled."""
        return plugin.state == PluginState.ENABLED

    def topLevelItemCount(self):
        """Compatibility method for external code."""
        return self.tree_widget.topLevelItemCount()

    def selectedItems(self):
        """Compatibility method for external code."""
        return self.tree_widget.selectedItems()

    def clear(self):
        """Compatibility method for external code."""
        return self.tree_widget.clear()

    def topLevelItem(self, index):
        """Compatibility method for external code."""
        return self.tree_widget.topLevelItem(index)

    def setCurrentItem(self, item):
        """Compatibility method for external code."""
        return self.tree_widget.setCurrentItem(item)

    def _on_selection_changed(self):
        """Handle selection changes."""
        selected_items = self.tree_widget.selectedItems()
        if selected_items:
            plugin = selected_items[0].data(0, QtCore.Qt.ItemDataRole.UserRole)
            self.plugin_selection_changed.emit(plugin)
        else:
            self.plugin_selection_changed.emit(None)

    def _on_item_clicked(self, item, column):
        """Handle item clicks (checkbox clicks)."""
        if column == COLUMN_ENABLED:  # Handle enabled checkbox
            plugin = item.data(COLUMN_ENABLED, QtCore.Qt.ItemDataRole.UserRole)
            if plugin:
                # Prevent rapid toggling of the same plugin
                if plugin.plugin_id in self._toggling_plugins:
                    return

                # Base toggle decision on actual plugin state
                if plugin.state == PluginState.ENABLED:
                    target_enabled = False  # Disable it
                elif plugin.state == PluginState.LOADED:
                    target_enabled = False  # Disable loaded plugins
                elif plugin.state in (PluginState.DISABLED, PluginState.DISCOVERED):
                    # Don't try to enable plugins that have failed before
                    if plugin.plugin_id in self._failed_enables:
                        return
                    target_enabled = True  # Enable it
                else:
                    return

                try:
                    self._toggling_plugins.add(plugin.plugin_id)
                    self._toggle_plugin(plugin, target_enabled)
                except Exception as e:
                    # Show error dialog to user
                    log.error("Failed to toggle plugin %s: %s", plugin.plugin_id, e, exc_info=True)
                    if target_enabled:
                        self._enable_error_dialog(plugin, str(e))
                    else:
                        self._disable_error_dialog(plugin, str(e))
                    # Track failed enable attempts
                    if target_enabled and "Already declared" in str(e):
                        self._failed_enables.add(plugin.plugin_id)
                finally:
                    # Clear failed enable tracking on successful disable
                    if not target_enabled and plugin.state == PluginState.DISABLED:
                        if plugin.plugin_id in self._failed_enables:
                            self._failed_enables.remove(plugin.plugin_id)

                    # Always update UI to reflect actual plugin state
                    actual_enabled = self._is_plugin_enabled(plugin)
                    item.setCheckState(
                        COLUMN_ENABLED,
                        QtCore.Qt.CheckState.Checked if actual_enabled else QtCore.Qt.CheckState.Unchecked,
                    )

                    # Remove from toggling set
                    self._toggling_plugins.discard(plugin.plugin_id)

                    # Emit signal for options dialog to refresh
                    action = "enabled" if actual_enabled else "disabled"
                    self.plugin_state_changed.emit(plugin, action)

    def _refresh_plugin_list(self):
        """Refresh the plugin list to reflect current state."""
        if self._refreshing:
            return

        self._refreshing = True
        try:
            plugins = self.plugin_manager.plugins

            # Use utility to temporarily disconnect signal during refresh
            with temporary_disconnect(self.tree_widget.itemClicked, self._on_item_clicked):
                self.populate_plugins(plugins)
        finally:
            self._refreshing = False

    def _toggle_plugin(self, plugin, enabled):
        """Toggle plugin enabled state."""
        if enabled:
            self.plugin_manager.enable_plugin(plugin)
        else:
            self.plugin_manager.disable_plugin(plugin)

    def _show_context_menu(self, position):
        """Show context menu for plugin list."""
        item = self.tree_widget.itemAt(position)
        if not item:
            return

        plugin = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if not plugin:
            return

        menu = QtWidgets.QMenu(self)

        # Enable/Disable action
        if self._is_plugin_enabled(plugin):
            disable_action = menu.addAction(_("Disable"))
            disable_action.triggered.connect(lambda: self._toggle_plugin_from_menu(plugin, False))
        else:
            enable_action = menu.addAction(_("Enable"))
            enable_action.triggered.connect(lambda: self._toggle_plugin_from_menu(plugin, True))

        menu.addSeparator()

        # Information action
        info_action = menu.addAction(_("Information"))
        info_action.triggered.connect(lambda: self._show_plugin_info(plugin))

        # Report bug action (if available)
        report_bugs_to = self._get_report_bugs_to(plugin)
        if report_bugs_to:
            report_bug_action = menu.addAction(_("Report a Bug"))
            report_bug_action.triggered.connect(lambda: self._open_report_bugs_to(report_bugs_to))

        menu.addSeparator()

        # Open plugin priority editor
        order_action = menu.addAction(_("Execution Order"))
        order_action.triggered.connect(self._show_execution_order_editor)

        # Show menu
        menu.exec(self.tree_widget.mapToGlobal(position))

    def _enable_error_dialog(self, plugin, errmsg):
        QtWidgets.QMessageBox.critical(
            self,
            _("Plugin Error"),
            _('Failed to enable plugin "{name}":\n{errmsg}').format(name=plugin.name(), errmsg=errmsg),
        )

    def _disable_error_dialog(self, plugin, errmsg):
        QtWidgets.QMessageBox.critical(
            self,
            _("Plugin Error"),
            _('Failed to disable plugin "{name}":\n{errmsg}').format(name=plugin.name(), errmsg=errmsg),
        )

    def _toggle_plugin_from_menu(self, plugin, enabled):
        """Toggle plugin from context menu."""
        try:
            self._toggle_plugin(plugin, enabled)
            # Refresh immediately
            self._refresh_plugin_list()
            # Emit signal for options dialog to refresh
            action = "enabled" if enabled else "disabled"
            self.plugin_state_changed.emit(plugin, action)
        except Exception as e:
            if enabled:
                self._enable_error_dialog(plugin, str(e))
            else:
                self._disable_error_dialog(plugin, str(e))

    def _get_report_bugs_to(self, plugin):
        """Get report_bugs_to value from plugin manifest."""
        return plugin.manifest.report_bugs_to if plugin.manifest else ''

    def _open_report_bugs_to(self, value):
        """Open bug report URL."""
        if not value:
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(value))

    def _show_plugin_info(self, plugin):
        """Show detailed plugin information dialog."""
        dialog = PluginInfoDialog(plugin, self)
        dialog.exec()

    def select_plugin(self, plugin):
        """Select a plugin in the plugin list"""
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            if plugin == item.data(COLUMN_ENABLED, QtCore.Qt.ItemDataRole.UserRole):
                self.tree_widget.setCurrentItem(item)

    def _show_execution_order_editor(self):
        "Open a dialog to allow the user to manually set the execution order of metadata processor plugins"

        # Get list of all registered metadata processor plugins
        plugins = []
        for processor in [album_metadata_processors, track_metadata_processors]:
            for info in processor.get_plugin_function_information():
                plugins.append(info)

        if not plugins:
            msg = QtWidgets.QMessageBox(self)
            msg.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            msg.setText(_("There were no installed metadata processing plugins found."))
            msg.setWindowTitle(_("No Data"))
            msg.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
            msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
            msg.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Ok)
            msg.show()
            return

        new_order, return_state = display_plugin_order_selector(parent=self)

        if return_state:
            config = get_config()
            config.setting['plugins3_exec_order'] = new_order


class UninstallPluginDialog(QtWidgets.QMessageBox):
    """Dialog for uninstalling plugins with purge option."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.setWindowTitle(_("Uninstall Plugin"))
        self.setup_ui()

    def setup_ui(self):
        """Setup the dialog UI."""
        self.setIcon(QtWidgets.QMessageBox.Icon.Warning)

        # Confirmation message
        self.setText(_('Are you sure you want to uninstall "{name}"?').format(name=self.plugin.name()))

        # Purge configuration checkbox
        self._purge_checkbox = QtWidgets.QCheckBox(_("Also remove plugin configuration"))
        self._purge_checkbox.setToolTip(_("Remove all saved settings and configuration for this plugin"))
        self.setCheckBox(self._purge_checkbox)

        # Buttons
        self._btn_confirm_uninstall = self.addButton(_("Yes, Uninstall!"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        self.addButton(QtWidgets.QMessageBox.StandardButton.Cancel)

    @property
    def purge_config(self) -> bool:
        return self._purge_checkbox.isChecked()

    @property
    def uninstall_confirmed(self) -> bool:
        return self.clickedButton() == self._btn_confirm_uninstall
