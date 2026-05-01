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

import json
import os
import shutil
import threading
import time

from picard import log
from picard.config import get_config


class MetadataCache:
    """Persistent disk cache for MusicBrainz API release responses.

    Stores full API response JSON keyed by release MBID.
    File mtime is used for TTL checking.

    Cache structure:
        {cache_dir}/{release_mbid}.json
    """

    def __init__(self, cache_dir: str, ttl_days: int = 7):
        self._cache_dir = cache_dir
        self._ttl_seconds = ttl_days * 86400
        self._lock = threading.Lock()
        os.makedirs(cache_dir, exist_ok=True)

    def get(self, mbid: str) -> dict | None:
        """Return cached release data or None if not cached/expired."""
        filepath = self._filepath(mbid)
        if not os.path.exists(filepath):
            return None
        # Check TTL
        try:
            mtime = os.path.getmtime(filepath)
        except OSError:
            return None
        if time.time() - mtime > self._ttl_seconds:
            try:
                os.unlink(filepath)
            except OSError:
                pass
            return None
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            # Corrupt cache file, remove it
            try:
                os.unlink(filepath)
            except OSError:
                pass
            return None

    def put(self, mbid: str, data: dict):
        """Store release data in cache."""
        filepath = self._filepath(mbid)
        with self._lock:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f)
            except OSError as e:
                log.warning("Failed to cache metadata for %s: %s", mbid, e)

    def clear(self):
        """Remove all cached metadata."""
        with self._lock:
            try:
                shutil.rmtree(self._cache_dir)
                os.makedirs(self._cache_dir, exist_ok=True)
            except OSError as e:
                log.warning("Failed to clear metadata cache: %s", e)

    def size(self) -> int:
        """Return total cache size in bytes."""
        total = 0
        try:
            for entry in os.scandir(self._cache_dir):
                if entry.is_file():
                    total += entry.stat().st_size
        except OSError:
            pass
        return total

    def _filepath(self, mbid: str) -> str:
        return os.path.join(self._cache_dir, f"{mbid}.json")


# Sentinel object used as _load_request value for cache hits
_CACHE_HIT_SENTINEL = object()

# Singleton instance
_metadata_cache: MetadataCache | None = None
_cache_init_lock = threading.Lock()


def get_metadata_cache() -> MetadataCache | None:
    """Return the global MetadataCache instance.

    Returns None if the cache is disabled in settings.
    Initializes the cache on first call.
    """
    global _metadata_cache
    if _metadata_cache is not None:
        return _metadata_cache

    with _cache_init_lock:
        # Double-check after acquiring lock
        if _metadata_cache is not None:
            return _metadata_cache

        config = get_config()
        if not config.setting['metadata_cache_enabled']:
            return None

        from PyQt6.QtCore import QStandardPaths
        cache_base = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.CacheLocation
        )
        cache_dir = os.path.join(cache_base, 'metadata')

        ttl_days = config.setting['metadata_cache_ttl_days']

        _metadata_cache = MetadataCache(cache_dir, ttl_days)
        log.info("Metadata disk cache initialized at %s (TTL %d days)",
                 cache_dir, ttl_days)
        return _metadata_cache


def reset_metadata_cache():
    """Reset the singleton so it will be re-initialized on next access.
    Useful for testing or when settings change.
    """
    global _metadata_cache
    with _cache_init_lock:
        _metadata_cache = None
