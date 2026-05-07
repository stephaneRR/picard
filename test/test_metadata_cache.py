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
import shutil
import tempfile
import time
import unittest

from picard.webservice.cache import MetadataCache


class TestMetadataCache(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='picard_test_metadata_cache_')
        self.cache = MetadataCache(self.tmpdir, ttl_days=7)
        self.test_mbid = 'f622e117-3b0a-4a49-8a2a-b1f6a8e4c2d0'
        self.test_data = {
            'release': {
                'id': self.test_mbid,
                'title': 'Test Album',
                'artist-credit': [{'name': 'Test Artist'}],
                'date': '2024-01-01',
                'media': [
                    {
                        'format': 'CD',
                        'track-count': 10,
                        'tracks': [{'title': f'Track {i}'} for i in range(1, 11)],
                    }
                ],
            }
        }

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_put_and_get(self):
        """Store release data and retrieve it."""
        self.cache.put(self.test_mbid, self.test_data)
        result = self.cache.get(self.test_mbid)
        self.assertIsNotNone(result)
        self.assertEqual(result['release']['id'], self.test_mbid)
        self.assertEqual(result['release']['title'], 'Test Album')

    def test_cache_miss(self):
        """Get returns None for non-existent MBID."""
        result = self.cache.get('00000000-0000-0000-0000-000000000000')
        self.assertIsNone(result)

    def test_ttl_expiration(self):
        """Expired entry returns None and is removed."""
        # Create a cache with a very short TTL
        cache = MetadataCache(self.tmpdir, ttl_days=0)
        cache._ttl_seconds = 1  # 1 second TTL for testing
        cache.put(self.test_mbid, self.test_data)

        # Verify it's there
        result = cache.get(self.test_mbid)
        self.assertIsNotNone(result)

        # Wait for expiration
        time.sleep(1.1)

        # Should be expired now
        result = cache.get(self.test_mbid)
        self.assertIsNone(result)

        # File should be removed
        filepath = cache._filepath(self.test_mbid)
        self.assertFalse(os.path.exists(filepath))

    def test_clear(self):
        """Clear removes all cached entries."""
        # Add multiple entries
        for i in range(5):
            mbid = f'00000000-0000-0000-0000-00000000000{i}'
            self.cache.put(mbid, {'release': {'id': mbid, 'title': f'Album {i}'}})

        # Verify they exist
        self.assertGreater(self.cache.size(), 0)

        # Clear
        self.cache.clear()

        # Verify empty
        self.assertEqual(self.cache.size(), 0)

        # Verify directory still exists
        self.assertTrue(os.path.isdir(self.tmpdir))

    def test_size(self):
        """Size returns correct total bytes."""
        # Empty cache
        self.assertEqual(self.cache.size(), 0)

        # Add an entry
        self.cache.put(self.test_mbid, self.test_data)

        # Size should match the file
        filepath = self.cache._filepath(self.test_mbid)
        expected_size = os.path.getsize(filepath)
        self.assertEqual(self.cache.size(), expected_size)
        self.assertGreater(self.cache.size(), 0)

    def test_invalid_json(self):
        """Corrupt cache file returns None."""
        filepath = self.cache._filepath(self.test_mbid)
        with open(filepath, 'w') as f:
            f.write('not valid json {{{')

        result = self.cache.get(self.test_mbid)
        self.assertIsNone(result)

        # Corrupt file should be removed
        self.assertFalse(os.path.exists(filepath))

    def test_overwrite_existing(self):
        """Putting same MBID overwrites previous data."""
        self.cache.put(self.test_mbid, self.test_data)

        updated_data = {
            'release': {
                'id': self.test_mbid,
                'title': 'Updated Album Title',
            }
        }
        self.cache.put(self.test_mbid, updated_data)

        result = self.cache.get(self.test_mbid)
        self.assertEqual(result['release']['title'], 'Updated Album Title')

    def test_creates_directory(self):
        """Cache creates directory if it doesn't exist."""
        new_dir = os.path.join(self.tmpdir, 'subdir', 'metadata')
        MetadataCache(new_dir)
        self.assertTrue(os.path.isdir(new_dir))

    def test_data_roundtrip_fidelity(self):
        """Ensure complex nested data survives JSON roundtrip."""
        complex_data = {
            'release': {
                'id': self.test_mbid,
                'title': 'Test éèê',
                'media': [
                    {
                        'tracks': [
                            {
                                'number': '1',
                                'title': 'Track with "quotes" & <brackets>',
                                'length': 234000,
                            }
                        ]
                    }
                ],
                'relations': [],
                'tags': [{'name': 'rock', 'count': 5}],
            }
        }
        self.cache.put(self.test_mbid, complex_data)
        result = self.cache.get(self.test_mbid)
        self.assertEqual(result, complex_data)


if __name__ == '__main__':
    unittest.main()
