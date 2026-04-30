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

import hashlib
import os
import shutil
import threading
import time

from PyQt6.QtCore import QStandardPaths

from picard import log
from picard.config import get_config


class CoverArtDiskCache:
    """Persistent disk cache for cover art images.

    Images are stored in a directory structure:
        {cache_dir}/{release_mbid}/{url_hash}_{image_type}.{ext}

    File mtime is used for TTL checking. Eviction is lazy (on put).
    """

    def __init__(self, cache_dir: str, max_size_mb: int = 1024, ttl_days: int = 30):
        self._cache_dir = cache_dir
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._ttl_seconds = ttl_days * 86400
        self._lock = threading.Lock()
        os.makedirs(cache_dir, exist_ok=True)

    @staticmethod
    def _url_hash(url: str) -> str:
        """Return a short hash of the URL for use as filename."""
        return hashlib.md5(url.encode('utf-8')).hexdigest()[:16]

    @staticmethod
    def _safe_type(image_type: str) -> str:
        """Sanitize image type string for use in filenames."""
        # Replace characters that are problematic in filenames
        return image_type.replace('/', '-').replace('\\', '-').replace(' ', '_')

    def _image_dir(self, release_id: str) -> str:
        return os.path.join(self._cache_dir, release_id)

    def _find_cached_file(self, release_id: str, url: str, image_type: str) -> str | None:
        """Find the cached file path if it exists, regardless of extension."""
        url_hash = self._url_hash(url)
        safe_type = self._safe_type(image_type)
        prefix = f"{url_hash}_{safe_type}."
        image_dir = self._image_dir(release_id)
        if not os.path.isdir(image_dir):
            return None
        try:
            for filename in os.listdir(image_dir):
                if filename.startswith(prefix):
                    return os.path.join(image_dir, filename)
        except OSError:
            pass
        return None

    def _image_path(self, release_id: str, url: str, image_type: str, extension: str) -> str:
        """Build the full path for a cached image."""
        url_hash = self._url_hash(url)
        safe_type = self._safe_type(image_type)
        filename = f"{url_hash}_{safe_type}{extension}"
        return os.path.join(self._image_dir(release_id), filename)

    def _is_expired(self, filepath: str) -> bool:
        """Check if a cached file has exceeded its TTL based on mtime."""
        try:
            mtime = os.path.getmtime(filepath)
            return (time.time() - mtime) > self._ttl_seconds
        except OSError:
            return True

    def get(self, release_id: str, image_url: str, image_type: str) -> bytes | None:
        """Return cached image data or None if not cached/expired."""
        filepath = self._find_cached_file(release_id, image_url, image_type)
        if filepath is None:
            return None
        if self._is_expired(filepath):
            with self._lock:
                try:
                    os.unlink(filepath)
                except OSError:
                    pass
            return None
        try:
            with open(filepath, 'rb') as f:
                return f.read()
        except OSError as e:
            log.debug("Cover art cache read error for %s: %s", filepath, e)
            return None

    def put(self, release_id: str, image_url: str, image_type: str,
            data: bytes, extension: str):
        """Store image data in cache."""
        with self._lock:
            try:
                image_dir = self._image_dir(release_id)
                os.makedirs(image_dir, exist_ok=True)
                filepath = self._image_path(release_id, image_url, image_type, extension)
                with open(filepath, 'wb') as f:
                    f.write(data)
                log.debug("Cover art cached: %s (%d bytes)", filepath, len(data))
            except OSError as e:
                log.warning("Cover art cache write error: %s", e)

    def has(self, release_id: str, image_url: str, image_type: str) -> bool:
        """Check if image is in cache without loading data."""
        filepath = self._find_cached_file(release_id, image_url, image_type)
        if filepath is None:
            return False
        if self._is_expired(filepath):
            with self._lock:
                try:
                    os.unlink(filepath)
                except OSError:
                    pass
            return False
        return True

    def clear(self):
        """Remove all cached images."""
        with self._lock:
            try:
                shutil.rmtree(self._cache_dir)
                os.makedirs(self._cache_dir, exist_ok=True)
                log.info("Cover art cache cleared")
            except OSError as e:
                log.warning("Error clearing cover art cache: %s", e)

    def size(self) -> int:
        """Return total cache size in bytes."""
        total = 0
        try:
            for dirpath, _dirnames, filenames in os.walk(self._cache_dir):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total += os.path.getsize(filepath)
                    except OSError:
                        pass
        except OSError:
            pass
        return total

    def evict_expired(self):
        """Remove entries older than TTL."""
        with self._lock:
            self._evict_expired_unlocked()

    def _evict_expired_unlocked(self):
        """Remove entries older than TTL (must be called with lock held)."""
        try:
            for dirpath, _dirnames, filenames in os.walk(self._cache_dir):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if self._is_expired(filepath):
                        try:
                            os.unlink(filepath)
                            log.debug("Evicted expired cache entry: %s", filepath)
                        except OSError:
                            pass
            # Remove empty directories
            self._cleanup_empty_dirs()
        except OSError:
            pass

    def evict_lru(self):
        """Remove oldest entries until under max_size."""
        with self._lock:
            self._evict_lru_unlocked()

    def _evict_lru_unlocked(self):
        """Remove oldest entries until under max_size (must be called with lock held)."""
        entries = []
        total_size = 0
        try:
            for dirpath, _dirnames, filenames in os.walk(self._cache_dir):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        stat = os.stat(filepath)
                        entries.append((filepath, stat.st_mtime, stat.st_size))
                        total_size += stat.st_size
                    except OSError:
                        pass
        except OSError:
            return

        if total_size <= self._max_size_bytes:
            return

        # Sort by mtime ascending (oldest first)
        entries.sort(key=lambda e: e[1])

        for filepath, _mtime, fsize in entries:
            if total_size <= self._max_size_bytes:
                break
            try:
                os.unlink(filepath)
                total_size -= fsize
                log.debug("Evicted LRU cache entry: %s", filepath)
            except OSError:
                pass

        self._cleanup_empty_dirs()

    def _cleanup_empty_dirs(self):
        """Remove empty subdirectories from the cache."""
        try:
            for dirpath, dirnames, filenames in os.walk(self._cache_dir, topdown=False):
                if dirpath == self._cache_dir:
                    continue
                if not dirnames and not filenames:
                    try:
                        os.rmdir(dirpath)
                    except OSError:
                        pass
        except OSError:
            pass


# Singleton instance
_cover_art_cache: CoverArtDiskCache | None = None
_cache_init_lock = threading.Lock()


def get_cover_art_cache() -> CoverArtDiskCache | None:
    """Return the global CoverArtDiskCache instance.

    Returns None if the cache is disabled in settings.
    Initializes the cache on first call.
    """
    global _cover_art_cache
    if _cover_art_cache is not None:
        return _cover_art_cache

    with _cache_init_lock:
        # Double-check after acquiring lock
        if _cover_art_cache is not None:
            return _cover_art_cache

        config = get_config()
        if not config.setting['cover_art_cache_enabled']:
            return None

        cache_base = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.CacheLocation
        )
        cache_dir = os.path.join(cache_base, 'covers')

        max_size_mb = config.setting['cover_art_cache_max_size_mb']
        ttl_days = config.setting['cover_art_cache_ttl_days']

        _cover_art_cache = CoverArtDiskCache(cache_dir, max_size_mb, ttl_days)
        log.info("Cover art disk cache initialized at %s (max %d MB, TTL %d days)",
                 cache_dir, max_size_mb, ttl_days)
        return _cover_art_cache


def reset_cover_art_cache():
    """Reset the singleton so it will be re-initialized on next access.
    Useful for testing or when settings change.
    """
    global _cover_art_cache
    with _cache_init_lock:
        _cover_art_cache = None
