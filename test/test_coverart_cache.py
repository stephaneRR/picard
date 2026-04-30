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

import os
import tempfile
import time
import unittest

from picard.coverart.cache import CoverArtDiskCache


class TestCoverArtDiskCache(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='picard_test_cache_')
        self.cache = CoverArtDiskCache(self.tmpdir, max_size_mb=10, ttl_days=30)
        # Minimal valid JPEG data (smallest valid JPEG)
        self.test_data = (
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01'
            b'\x00\x01\x00\x00\xff\xd9'
        )
        self.release_id = 'abc123-def456-ghi789'
        self.image_url = 'https://coverartarchive.org/release/abc123/front-500.jpg'
        self.image_type = 'front'

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_put_and_get(self):
        """Store an image and retrieve it."""
        self.cache.put(self.release_id, self.image_url, self.image_type,
                       self.test_data, '.jpg')
        result = self.cache.get(self.release_id, self.image_url, self.image_type)
        self.assertEqual(result, self.test_data)

    def test_cache_miss(self):
        """Get returns None for non-existent entry."""
        result = self.cache.get('nonexistent', 'http://example.com/img.jpg', 'front')
        self.assertIsNone(result)

    def test_has_existing(self):
        """has() returns True for existing entry."""
        self.cache.put(self.release_id, self.image_url, self.image_type,
                       self.test_data, '.jpg')
        self.assertTrue(self.cache.has(self.release_id, self.image_url, self.image_type))

    def test_has_missing(self):
        """has() returns False for missing entry."""
        self.assertFalse(self.cache.has('nonexistent', 'http://example.com/img.jpg', 'front'))

    def test_ttl_expiration(self):
        """Entry expires after TTL."""
        # Create cache with 0-second TTL (everything expires immediately)
        cache = CoverArtDiskCache(self.tmpdir, max_size_mb=10, ttl_days=0)
        cache.put(self.release_id, self.image_url, self.image_type,
                  self.test_data, '.jpg')

        # Set mtime to the past
        filepath = cache._find_cached_file(self.release_id, self.image_url, self.image_type)
        self.assertIsNotNone(filepath)
        os.utime(filepath, (time.time() - 100, time.time() - 100))

        result = cache.get(self.release_id, self.image_url, self.image_type)
        self.assertIsNone(result)

    def test_clear(self):
        """clear() removes all entries."""
        self.cache.put(self.release_id, self.image_url, self.image_type,
                       self.test_data, '.jpg')
        self.cache.put('other-release', 'http://example.com/other.jpg', 'back',
                       self.test_data, '.jpg')

        self.cache.clear()

        self.assertIsNone(self.cache.get(self.release_id, self.image_url, self.image_type))
        self.assertIsNone(self.cache.get('other-release', 'http://example.com/other.jpg', 'back'))
        # Cache dir should still exist (recreated)
        self.assertTrue(os.path.isdir(self.tmpdir))

    def test_size(self):
        """size() returns correct value."""
        self.assertEqual(self.cache.size(), 0)

        self.cache.put(self.release_id, self.image_url, self.image_type,
                       self.test_data, '.jpg')

        self.assertEqual(self.cache.size(), len(self.test_data))

    def test_size_multiple_entries(self):
        """size() accumulates across entries."""
        data2 = self.test_data * 2
        self.cache.put(self.release_id, self.image_url, self.image_type,
                       self.test_data, '.jpg')
        self.cache.put('other-release', 'http://example.com/other.jpg', 'back',
                       data2, '.jpg')

        self.assertEqual(self.cache.size(), len(self.test_data) + len(data2))

    def test_overwrite_same_key(self):
        """Putting the same key twice overwrites the data."""
        self.cache.put(self.release_id, self.image_url, self.image_type,
                       self.test_data, '.jpg')
        new_data = b'\xff' * 100
        self.cache.put(self.release_id, self.image_url, self.image_type,
                       new_data, '.jpg')

        result = self.cache.get(self.release_id, self.image_url, self.image_type)
        self.assertEqual(result, new_data)

    def test_different_types_same_release(self):
        """Different image types for the same release are stored separately."""
        data_front = self.test_data
        data_back = self.test_data * 2
        self.cache.put(self.release_id, self.image_url, 'front',
                       data_front, '.jpg')
        self.cache.put(self.release_id, 'http://example.com/back.jpg', 'back',
                       data_back, '.jpg')

        self.assertEqual(
            self.cache.get(self.release_id, self.image_url, 'front'),
            data_front,
        )
        self.assertEqual(
            self.cache.get(self.release_id, 'http://example.com/back.jpg', 'back'),
            data_back,
        )

    def test_evict_expired(self):
        """evict_expired removes old entries."""
        cache = CoverArtDiskCache(self.tmpdir, max_size_mb=10, ttl_days=0)
        cache.put(self.release_id, self.image_url, self.image_type,
                  self.test_data, '.jpg')

        # Set mtime to the past
        filepath = cache._find_cached_file(self.release_id, self.image_url, self.image_type)
        os.utime(filepath, (time.time() - 100, time.time() - 100))

        cache.evict_expired()
        self.assertIsNone(cache._find_cached_file(self.release_id, self.image_url, self.image_type))

    def test_evict_lru(self):
        """evict_lru removes oldest entries to stay under max_size."""
        # Create a tiny cache (100 bytes max)
        cache = CoverArtDiskCache(self.tmpdir, max_size_mb=0, ttl_days=30)
        cache._max_size_bytes = 100  # Override for testing

        # Add entries that exceed 100 bytes total
        data = b'x' * 60
        cache.put('release1', 'http://example.com/1.jpg', 'front', data, '.jpg')
        # Set older mtime so this one gets evicted first
        filepath1 = cache._find_cached_file('release1', 'http://example.com/1.jpg', 'front')
        os.utime(filepath1, (time.time() - 200, time.time() - 200))

        cache.put('release2', 'http://example.com/2.jpg', 'front', data, '.jpg')

        # Total is now 120 bytes, exceeding 100
        cache.evict_lru()

        # Oldest entry should be evicted
        self.assertIsNone(cache.get('release1', 'http://example.com/1.jpg', 'front'))
        # Newer entry should remain
        self.assertEqual(cache.get('release2', 'http://example.com/2.jpg', 'front'), data)

    def test_url_hash_consistency(self):
        """Same URL always produces the same hash."""
        url = 'https://coverartarchive.org/release/abc123/front-500.jpg'
        hash1 = CoverArtDiskCache._url_hash(url)
        hash2 = CoverArtDiskCache._url_hash(url)
        self.assertEqual(hash1, hash2)

    def test_special_characters_in_type(self):
        """Image types with special characters are handled safely."""
        self.cache.put(self.release_id, self.image_url, 'front/back',
                       self.test_data, '.jpg')
        result = self.cache.get(self.release_id, self.image_url, 'front/back')
        self.assertEqual(result, self.test_data)


if __name__ == '__main__':
    unittest.main()
