# -*- coding: utf-8 -*-
#
# Picard, the next-generation MusicBrainz tagger
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

from test.picardtestcase import PicardTestCase

from picard.file import File


class FakeMutagenFile:
    """Minimal fake Mutagen file object for testing cache behavior."""
    def __init__(self):
        self.tags = {'title': ['Test']}


class CacheTestHost:
    """Minimal host object that has the cache methods from File.

    We cannot instantiate File directly (requires tagger context),
    so we copy the cache methods for isolated testing.
    """
    _cache_mutagen_file = File._cache_mutagen_file
    _get_cached_mutagen_file = File._get_cached_mutagen_file


class TestMutagenCache(PicardTestCase):

    def setUp(self):
        super().setUp()
        self.temp_files = set()
        self.file_obj = CacheTestHost()

    def tearDown(self):
        for fname in self.temp_files:
            try:
                os.remove(fname)
            except OSError:
                pass
        super().tearDown()

    def _write_temp(self, contents=b"hello"):
        fd, fname = tempfile.mkstemp()
        self.temp_files.add(fname)
        with os.fdopen(fd, "wb") as f:
            f.write(contents)
        return fname

    def test_cache_and_retrieve(self):
        """Cached mutagen file is returned when mtime matches."""
        fname = self._write_temp()
        fake_file = FakeMutagenFile()
        self.file_obj._cache_mutagen_file(fake_file, fname)
        result = self.file_obj._get_cached_mutagen_file(fname)
        self.assertIs(result, fake_file)

    def test_cache_cleared_after_get(self):
        """Cache is cleared after retrieval (one-time use)."""
        fname = self._write_temp()
        fake_file = FakeMutagenFile()
        self.file_obj._cache_mutagen_file(fake_file, fname)
        self.file_obj._get_cached_mutagen_file(fname)
        # Second retrieval should return None
        result = self.file_obj._get_cached_mutagen_file(fname)
        self.assertIsNone(result)

    def test_cache_invalidated_on_mtime_change(self):
        """Cache returns None when file mtime has changed."""
        fname = self._write_temp()
        fake_file = FakeMutagenFile()
        self.file_obj._cache_mutagen_file(fake_file, fname)
        # Modify the file to change mtime
        time.sleep(0.05)
        with open(fname, 'wb') as f:
            f.write(b"modified content")
        result = self.file_obj._get_cached_mutagen_file(fname)
        self.assertIsNone(result)

    def test_cache_cleared_after_mtime_mismatch(self):
        """Cache is cleared even when mtime check fails."""
        fname = self._write_temp()
        fake_file = FakeMutagenFile()
        self.file_obj._cache_mutagen_file(fake_file, fname)
        # Modify the file
        time.sleep(0.05)
        with open(fname, 'wb') as f:
            f.write(b"modified content")
        self.file_obj._get_cached_mutagen_file(fname)
        # Verify cache attributes are cleared
        self.assertIsNone(getattr(self.file_obj, '_cached_mutagen_file', None))
        self.assertIsNone(getattr(self.file_obj, '_cached_mutagen_mtime', None))

    def test_no_cache_returns_none(self):
        """Returns None when no file has been cached."""
        fname = self._write_temp()
        result = self.file_obj._get_cached_mutagen_file(fname)
        self.assertIsNone(result)

    def test_cache_cleared_on_file_deleted(self):
        """Cache returns None and clears when the file no longer exists."""
        fname = self._write_temp()
        fake_file = FakeMutagenFile()
        self.file_obj._cache_mutagen_file(fake_file, fname)
        os.remove(fname)
        self.temp_files.discard(fname)
        result = self.file_obj._get_cached_mutagen_file(fname)
        self.assertIsNone(result)
        # Cache should still be cleared
        self.assertIsNone(getattr(self.file_obj, '_cached_mutagen_file', None))

    def test_tags_restored_after_load_mutation(self):
        """Original tags are restored even if _load replaced them."""
        fname = self._write_temp()
        fake_file = FakeMutagenFile()
        original_tags = fake_file.tags
        self.file_obj._cache_mutagen_file(fake_file, fname)
        # Simulate what _load does: replace tags with a plain dict
        fake_file.tags = {}
        result = self.file_obj._get_cached_mutagen_file(fname)
        self.assertIs(result, fake_file)
        # Tags should be restored to the original
        self.assertIs(result.tags, original_tags)


if __name__ == '__main__':
    unittest.main()
