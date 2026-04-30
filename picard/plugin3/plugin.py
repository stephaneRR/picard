# -*- coding: utf-8 -*-
#
# Picard, the next-generation MusicBrainz tagger
#
# Copyright (C) 2024 Laurent Monin
# Copyright (C) 2024-2025 Philipp Wolfer
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

from enum import Enum
import hashlib
import importlib.util
from pathlib import Path
import sys
import types

from picard import log
from picard.extension_points import unregister_module_extensions
from picard.i18n import sort_key
from picard.plugin3.api import PluginApi
from picard.plugin3.manifest import PluginManifest


def short_commit_id(commit_id):
    """Return shortened commit ID for display.

    Uses first 7 characters by default. Can be adjusted for future
    git versions that use longer hashes (e.g., SHA-256).
    """
    if not commit_id:
        return ''
    return commit_id[:7]


def hash_string(text):
    """Generate SHA1 hash of a string for use in filenames.

    Args:
        text: String to hash

    Returns:
        str: Full SHA1 hash (40 characters)
    """

    return hashlib.sha1(text.encode()).hexdigest()


class PluginState(Enum):
    """Plugin lifecycle states."""

    DISCOVERED = 'discovered'  # Found on disk, not yet loaded
    LOADED = 'loaded'  # Module loaded, not enabled
    ENABLED = 'enabled'  # Enabled and active
    DISABLED = 'disabled'  # Explicitly disabled
    ERROR = 'error'  # Failed to load or enable


class PluginSourceSyncError(Exception):
    pass


class PluginAlreadyEnabledError(Exception):
    """Raised when trying to enable an already enabled plugin."""

    def __init__(self, plugin_id):
        self.plugin_id = plugin_id
        super().__init__(f"Plugin {plugin_id} is already enabled")


class PluginAlreadyDisabledError(Exception):
    """Raised when trying to disable an already disabled plugin."""

    def __init__(self, plugin_id):
        self.plugin_id = plugin_id
        super().__init__(f"Plugin {plugin_id} is already disabled")


class PluginSource:
    """Abstract class for plugin sources"""

    def sync(self, target_directory: Path):
        raise NotImplementedError


class PluginSourceLocal(PluginSource):
    """Plugin is stored in a local directory, but is not a git repo"""

    def sync(self, target_directory: Path):
        # TODO: copy tree to plugin directory (?)
        pass


class Plugin:
    local_path: Path | None = None
    remote_url: str | None = None
    ref: str | None = None
    module_name: str | None = None
    manifest: PluginManifest | None = None
    state: PluginState | None = None
    _module: types.ModuleType | None = None

    def __init__(self, plugins_dir: Path, plugin_id: str, uuid: str | None = None):
        assert plugin_id, "Plugin ID cannot be empty!"
        self.plugin_id = plugin_id
        self.module_name = f'picard.plugins.{self.plugin_id}'
        self.local_path = plugins_dir.joinpath(self.plugin_id)
        self.state = PluginState.DISCOVERED
        self.uuid = uuid

    def __lt__(self, other):
        return sort_key(self.name()) < sort_key(other.name())

    def sync(self, plugin_source: PluginSource | None = None):
        """Sync plugin source"""
        if plugin_source:
            assert self.local_path is not None, "Plugin local_path must be set"
            try:
                plugin_source.sync(self.local_path)
            except Exception as e:
                raise PluginSourceSyncError(e) from e

    def read_manifest(self):
        """Reads metadata for the plugin from the plugin's MANIFEST.toml"""
        from picard.plugin3.errors import (
            PluginManifestInvalidError,
            PluginManifestReadError,
        )

        self.uuid = None
        try:
            manifest_path = self.local_path.joinpath('MANIFEST.toml')
            with open(manifest_path, 'rb') as manifest_file:
                self.manifest = PluginManifest(self.plugin_id, manifest_file)
        except Exception as e:
            raise PluginManifestReadError(e, manifest_path) from e

        # Validate manifest
        errors = self.manifest.validate()
        if errors:
            raise PluginManifestInvalidError(errors)

        # Add a shortcut
        self.uuid = self.manifest.uuid

    def has_versioning(self, registry=None, is_tag_installation=False):
        """Check if plugin supports version-based updates.

        Args:
            registry: PluginRegistry instance to check for versioning_scheme
            is_tag_installation: Whether plugin was installed from a tag

        Returns:
            bool: True if plugin supports versioning (has registry versioning_scheme
                  or is a local/URL plugin installed from tags)
        """
        if registry and self.uuid:
            registry_plugin = registry.find_plugin(uuid=self.uuid)
            if registry_plugin and registry_plugin.versioning_scheme:
                return True

        # Local/URL plugins installed from tags support versioning (assume semver)
        return is_tag_installation and not (registry and registry.find_plugin(uuid=self.uuid))

    def get_versioning_scheme(self, registry=None):
        """Get versioning scheme for this plugin.

        Args:
            registry: PluginRegistry instance to check for versioning_scheme

        Returns:
            str: Versioning scheme ('semver', 'calver', 'regex:pattern') or 'semver'
                 for local plugins, empty string if no versioning support
        """
        if registry and self.uuid:
            registry_plugin = registry.find_plugin(uuid=self.uuid)
            if registry_plugin and registry_plugin.versioning_scheme:
                return registry_plugin.versioning_scheme

        # Default to semver for local/URL plugins (when they have versioning support)
        return 'semver'

    def get_current_commit_id(self, short=False):
        """Get the current commit ID of the plugin if it's a git repository.

        Returns None since git backend has been removed.
        """
        return None

    def load_module(self):
        """Load corresponding module from source path"""
        if self.state == PluginState.LOADED:
            return self._module
        if self.state == PluginState.ENABLED:
            raise PluginAlreadyEnabledError(self.plugin_id)

        module_file = self.local_path.joinpath('__init__.py')
        spec = importlib.util.spec_from_file_location(self.module_name, module_file)
        module = importlib.util.module_from_spec(spec)
        sys.modules[self.module_name] = module
        spec.loader.exec_module(module)
        self._module = module
        self.state = PluginState.LOADED

        return module

    def enable(self, tagger) -> None:
        """Enable the plugin"""
        if self.state == PluginState.ENABLED:
            raise PluginAlreadyEnabledError(self.plugin_id)

        assert self.manifest is not None, "Plugin manifest must be loaded before enabling"
        api = PluginApi(self.manifest, tagger)
        api._plugin_module = self._module
        api._plugin_dir = self.local_path
        api._load_translations()
        api._install_qt_translator()

        # Register API instance for get_api()
        module_name = getattr(self._module, '__name__', None)
        if module_name:
            # Check if there's an existing API instance (from UI components)
            # and reload its translations to reflect any updates
            existing_api = PluginApi._instances.get(module_name)
            if existing_api and existing_api._plugin_dir == self.local_path:
                existing_api._plugin_module = self._module
                existing_api.reload_translations()

            PluginApi._instances[module_name] = api

        # Log plugin info
        version = self.manifest.version if self.manifest else None
        version_str = f" v{version}" if version else ""
        api.logger.info(f"Enabling plugin {self.plugin_id}{version_str}")

        assert self._module is not None, "Plugin module must be loaded before enabling"
        self._module.enable(api)
        self.state = PluginState.ENABLED

    def disable(self) -> None:
        """Disable the plugin"""
        if self.state == PluginState.DISABLED:
            raise PluginAlreadyDisabledError(self.plugin_id)

        if self._module is not None and hasattr(self._module, 'disable'):
            self._module.disable()
        unregister_module_extensions(self.plugin_id)

        # Cleanup API instance registry - find and remove by module reference
        for name, api in list(PluginApi._instances.items()):
            if api._plugin_module is self._module:
                api._remove_qt_translator()
                del PluginApi._instances[name]
                # Remove from cache (entries for this module and submodules)
                for key in list(PluginApi._module_cache):
                    if key == name or key.startswith(name + '.'):
                        del PluginApi._module_cache[key]
                break

        # Clear module from sys.modules to force reload on next enable
        if self.module_name and self.module_name in sys.modules:
            del sys.modules[self.module_name]
        # Also clear any submodules
        if self.module_name:
            module_prefix = self.module_name + '.'
            for module_name in list(sys.modules.keys()):
                if module_name.startswith(module_prefix):
                    del sys.modules[module_name]

        self.state = PluginState.DISABLED

    def name(self):
        """Returns translated plugin name if possible, else plugin_id"""
        try:
            return self.manifest.name_i18n()
        except Exception as e:
            log.error("Failed to get plugin %s's name: %s", self, e)
            return str(self)

    def __str__(self):
        """Returns plugin id"""
        return self.plugin_id
