# -*- coding: utf-8 -*-
#
# Picard, the next-generation MusicBrainz tagger
#
# Copyright (C) 2025 Philipp Wolfer, Laurent Monin
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

"""Plugin metadata storage and retrieval."""

from dataclasses import (
    asdict,
    dataclass,
)
from typing import TYPE_CHECKING

from picard import log
from picard.config import get_config


if TYPE_CHECKING:
    pass


@dataclass
class PluginMetadata:
    """Plugin metadata stored in config."""

    url: str
    ref: str
    commit: str
    name: str = ''
    uuid: str | None = None
    original_url: str | None = None
    original_uuid: str | None = None
    ref_type: str | None = None  # 'tag' or 'branch' to indicate installation method

    def to_dict(self):
        """Convert to dict for config storage, excluding None values."""
        data = {k: v for k, v in asdict(self).items() if v is not None}
        return data

    @classmethod
    def from_dict(cls, data: dict):
        """Create PluginMetadata from dict."""
        # Filter unknown fields and create instance
        filtered_data = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**filtered_data)


class PluginMetadataManager:
    """Manages plugin metadata storage and retrieval."""

    def __init__(self, registry):
        self._registry = registry

    def get_plugin_metadata(self, uuid: str):
        """Get metadata for a plugin by UUID.

        Returns:
            PluginMetadata object or None if not found
        """
        metadata_dict = get_config().setting['plugins3_metadata'].get(str(uuid))
        if not metadata_dict:
            return None
        return PluginMetadata.from_dict(metadata_dict)

    def save_plugin_metadata(self, metadata):
        """Save or update plugin metadata.

        Args:
            metadata: PluginMetadata object with uuid, url, ref, commit, etc.
        """
        config = get_config()
        # Get the current dict, modify it, and set it back to trigger save
        metadata_dict = config.setting['plugins3_metadata'] or {}
        metadata_dict[metadata.uuid] = metadata.to_dict()
        config.setting['plugins3_metadata'] = metadata_dict
        # Force write to disk immediately (if sync is available)
        if hasattr(config, 'sync'):
            config.sync()

    def find_plugin_by_url(self, url: str):
        """Find plugin metadata by URL.

        Args:
            url: Plugin source URL

        Returns:
            PluginMetadata: Plugin metadata or None if not found
        """
        metadata = get_config().setting['plugins3_metadata']
        if not url:
            return None
        for item in metadata.values():
            if item.get('url', '') == url:
                return PluginMetadata.from_dict(item)
        return None

    def check_redirects(self, old_url, old_uuid):
        """Check if plugin was redirected to new URL and/or UUID.

        Args:
            old_url: Original URL
            old_uuid: Original UUID

        Returns:
            tuple: (new_url, new_uuid, redirected) where redirected is True if changed
        """
        plugin = self._registry.resolve_redirect(url=old_url, uuid=old_uuid)
        if plugin:
            new_url = plugin.git_url or old_url
            new_uuid = plugin.uuid or old_uuid
            log.info('Plugin redirected: url %s -> %s, uuid %s -> %s', old_url, new_url, old_uuid, new_uuid)
            return new_url, new_uuid, True
        return old_url, old_uuid, False

    def get_original_metadata(self, redirected, old_url, old_uuid):
        """Get original metadata before redirect.

        Preserves the earliest original values across chained redirects
        (A->B->C keeps A as the original).

        Args:
            redirected: Whether plugin was redirected
            old_url: Original URL
            old_uuid: Original UUID

        Returns:
            tuple: (original_url, original_uuid) from metadata or old values if not found
        """
        if not redirected:
            return old_url, old_uuid

        # Try to find existing metadata to preserve earliest original values
        old_metadata = self.get_plugin_metadata(old_uuid)
        if not old_metadata:
            old_metadata = self.find_plugin_by_url(old_url)

        if old_metadata:
            # If already redirected before, keep the earliest original
            if old_metadata.original_url:
                return old_metadata.original_url, old_metadata.original_uuid or old_uuid
            return old_metadata.url or old_url, old_metadata.uuid or old_uuid

        return old_url, old_uuid

    def get_plugin_registry_id(self, plugin):
        """Get registry ID for a plugin by looking it up in the current registry.

        Args:
            plugin: Plugin to get registry ID for

        Returns:
            str: Registry ID or None if not in registry
        """
        if not plugin.uuid:
            return None

        # Look up plugin in registry by UUID
        registry_plugin = self._registry.find_plugin(uuid=str(plugin.uuid))
        if registry_plugin:
            return registry_plugin.get('id')

        return None
