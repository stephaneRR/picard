# -*- coding: utf-8 -*-
#
# Picard, the next-generation MusicBrainz tagger
#
# Copyright (C) 2024-2025 Laurent Monin, Philipp Wolfer
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

"""Minimal plugin manager for loading, enabling, and disabling local plugins.

This replaces the git-based PluginManager from picard.plugin3.manager,
keeping only local filesystem plugin discovery and lifecycle management.
"""

from pathlib import Path

from PyQt6.QtCore import (
    QObject,
    pyqtSignal,
)

from picard import log
from picard.config import get_config
from picard.plugin3.errors import (
    PluginManifestInvalidError,
    PluginManifestReadError,
)
from picard.plugin3.plugin import (
    Plugin,
    PluginState,
)
from picard.plugin3.registry import PluginRegistry


class PluginManager(QObject):
    """Minimal plugin manager for local plugins.

    Handles plugin discovery, loading, enabling, and disabling from
    local directories. Does not support git-based installation or updates.
    """

    # Signals
    plugin_state_changed = pyqtSignal()
    plugin_installed = pyqtSignal()
    plugin_uninstalled = pyqtSignal()
    plugin_ref_switched = pyqtSignal()
    refresh_updates_available = pyqtSignal()
    plugin_update_checks_complete = pyqtSignal(dict)

    def __init__(self, tagger):
        super().__init__(tagger)
        self._tagger = tagger
        self._plugins = []
        self._plugins_dir = None
        self._enabled_plugins = set()
        self._init_failed_plugins = []
        self._registry = PluginRegistry(
            cache_dir=get_config().setting.get('plugin_registry_cache_dir')
        )

    @property
    def plugins(self):
        """Get list of all discovered plugins."""
        return self._plugins

    def add_directory(self, path, primary=False):
        """Add a plugin directory to scan for plugins.

        Args:
            path: Directory path containing plugins
            primary: If True, this is the main plugin directory
        """
        self._plugins_dir = Path(path)
        if not self._plugins_dir.exists():
            self._plugins_dir.mkdir(parents=True, exist_ok=True)
        self._discover_plugins()

    def _discover_plugins(self):
        """Discover plugins in the plugins directory."""
        if not self._plugins_dir or not self._plugins_dir.exists():
            return

        self._plugins = []
        for entry in sorted(self._plugins_dir.iterdir()):
            if not entry.is_dir():
                continue
            # Skip hidden directories and __pycache__
            if entry.name.startswith('.') or entry.name == '__pycache__':
                continue
            # Check if it has a MANIFEST.toml or __init__.py
            if not (entry / 'MANIFEST.toml').exists():
                continue

            plugin = Plugin(self._plugins_dir, entry.name)
            try:
                plugin.read_manifest()
                self._plugins.append(plugin)
            except (PluginManifestReadError, PluginManifestInvalidError) as e:
                log.warning('Failed to read manifest for plugin %s: %s', entry.name, e)
                self._init_failed_plugins.append((entry.name, str(e)))

    def init_plugins(self):
        """Initialize and enable plugins based on config.

        Returns:
            list: List of (name, reason) tuples for blacklisted plugins
        """
        config = get_config()
        enabled_plugins = config.setting.get('plugins3_enabled', [])
        blacklisted = []

        for plugin in self._plugins:
            if not plugin.uuid:
                continue

            # Check blacklist
            is_blacklisted, reason = self._registry.is_blacklisted(
                plugin.remote_url or '', plugin.uuid
            )
            if is_blacklisted:
                blacklisted.append((plugin.name(), reason))
                plugin.state = PluginState.DISABLED
                continue

            # Enable plugin if in enabled list
            if plugin.uuid in enabled_plugins:
                try:
                    plugin.load_module()
                    plugin.enable(self._tagger)
                    self._enabled_plugins.add(plugin.uuid)
                except Exception as e:
                    log.error('Failed to enable plugin %s: %s', plugin.plugin_id, e)
                    plugin.state = PluginState.ERROR
                    self._init_failed_plugins.append((plugin.plugin_id, str(e)))

        return blacklisted

    def enable_plugin(self, plugin):
        """Enable a plugin.

        Args:
            plugin: Plugin object to enable
        """
        config = get_config()
        try:
            if plugin.state != PluginState.LOADED:
                plugin.load_module()
            plugin.enable(self._tagger)
            self._enabled_plugins.add(plugin.uuid)

            # Update config
            enabled = list(config.setting.get('plugins3_enabled', []))
            if plugin.uuid not in enabled:
                enabled.append(plugin.uuid)
                config.setting['plugins3_enabled'] = enabled

            self.plugin_state_changed.emit()
        except Exception as e:
            log.error('Failed to enable plugin %s: %s', plugin.plugin_id, e)
            plugin.state = PluginState.ERROR
            raise

    def disable_plugin(self, plugin):
        """Disable a plugin.

        Args:
            plugin: Plugin object to disable
        """
        config = get_config()
        try:
            plugin.disable()
            self._enabled_plugins.discard(plugin.uuid)

            # Update config
            enabled = list(config.setting.get('plugins3_enabled', []))
            if plugin.uuid in enabled:
                enabled.remove(plugin.uuid)
                config.setting['plugins3_enabled'] = enabled

            self.plugin_state_changed.emit()
        except Exception as e:
            log.error('Failed to disable plugin %s: %s', plugin.plugin_id, e)
            raise

    def plugin_id_to_plugin(self, plugin_id):
        """Find a plugin by its ID.

        Args:
            plugin_id: Plugin ID string

        Returns:
            Plugin or None
        """
        for plugin in self._plugins:
            if plugin.plugin_id == plugin_id:
                return plugin
        return None

    def check_updates(self, skip_fetch=False, include_plugins=None):
        """Check for plugin updates.

        Returns empty dict since git-based updates are no longer supported.

        Returns:
            dict: Empty dict (no updates without git)
        """
        return {}

    def refresh_all_plugin_refs(self):
        """Refresh refs for all plugins.

        No-op since git-based refs are no longer supported.
        """
        pass

    def refresh_registry_and_caches(self, callback=None):
        """Refresh the plugin registry.

        Args:
            callback: Optional callback(success, error)
        """
        self._registry.fetch_registry(use_cache=False, callback=callback)

    def get_plugin_remote_url(self, plugin):
        """Get remote URL for a plugin from metadata.

        Returns None since git-based metadata is no longer available.
        """
        return None

    def get_plugin_version_display(self, plugin):
        """Get version display string for a plugin."""
        if plugin.manifest and plugin.manifest.version:
            return str(plugin.manifest.version)
        return ''

    def get_plugin_versioning_scheme(self, plugin):
        """Get versioning scheme for a plugin."""
        return plugin.get_versioning_scheme(self._registry)

    def get_plugin_git_info(self, metadata):
        """Get git info display string. Returns empty string (git removed)."""
        return ''

    def _get_plugin_metadata(self, uuid):
        """Get plugin metadata by UUID. Returns None (git metadata removed)."""
        return None

    def _get_plugin_uuid(self, plugin):
        """Get UUID for a plugin."""
        return plugin.uuid
