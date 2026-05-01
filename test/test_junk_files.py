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
from unittest.mock import (
    MagicMock,
    patch,
)

from test.picardtestcase import PicardTestCase

from picard.file import File


class DeleteJunkFilesTest(PicardTestCase):

    def setUp(self):
        super().setUp()
        self.tagger.acoustidmanager = MagicMock()
        self.file = File('somepath/somefile.mp3')

    def _create_junk_dir(self, filenames):
        """Create a temp dir with the given filenames inside."""
        tmpdir = self.mktmpdir()
        for name in filenames:
            open(os.path.join(tmpdir, name), 'a').close()
        return tmpdir

    def _make_config(self, enabled=True, pattern='*.url *.nfo *.m3u'):
        """Create a mock config object."""
        config = MagicMock()
        config.setting = {
            'delete_junk_files': enabled,
            'delete_junk_files_pattern': pattern,
        }
        return config

    @patch('picard.file.send2trash')
    def test_delete_junk_files_matches_pattern(self, mock_send2trash):
        """Files matching pattern are sent to trash."""
        tmpdir = self._create_junk_dir(['info.nfo', 'playlist.m3u', 'music.mp3'])
        config = self._make_config(enabled=True, pattern='*.nfo *.m3u')
        self.file._delete_junk_files(tmpdir, config)
        # mp3 should not be trashed, nfo and m3u should
        trashed_files = {os.path.basename(call[0][0]) for call in mock_send2trash.call_args_list}
        self.assertIn('info.nfo', trashed_files)
        self.assertIn('playlist.m3u', trashed_files)
        self.assertNotIn('music.mp3', trashed_files)

    @patch('picard.file.send2trash')
    def test_delete_junk_files_no_match(self, mock_send2trash):
        """Files not matching pattern are kept."""
        tmpdir = self._create_junk_dir(['music.mp3', 'album.flac'])
        config = self._make_config(enabled=True, pattern='*.nfo *.m3u *.url')
        self.file._delete_junk_files(tmpdir, config)
        mock_send2trash.assert_not_called()

    @patch('picard.file.send2trash')
    def test_delete_junk_files_disabled(self, mock_send2trash):
        """When setting is off, nothing is deleted."""
        tmpdir = self._create_junk_dir(['info.nfo', 'playlist.m3u'])
        config = self._make_config(enabled=False, pattern='*.nfo *.m3u')
        self.file._delete_junk_files(tmpdir, config)
        mock_send2trash.assert_not_called()

    @patch('picard.file.send2trash')
    def test_delete_junk_files_empty_pattern(self, mock_send2trash):
        """Empty pattern means nothing is deleted."""
        tmpdir = self._create_junk_dir(['info.nfo', 'playlist.m3u'])
        config = self._make_config(enabled=True, pattern='')
        self.file._delete_junk_files(tmpdir, config)
        mock_send2trash.assert_not_called()

    @patch('picard.file.send2trash')
    def test_delete_junk_files_loaded_file_not_deleted(self, mock_send2trash):
        """File loaded in tagger.files should not be deleted."""
        tmpdir = self._create_junk_dir(['info.nfo'])
        nfo_path = os.path.join(tmpdir, 'info.nfo')
        # Simulate that the file is loaded in the tagger
        self.tagger.files[nfo_path] = MagicMock()
        config = self._make_config(enabled=True, pattern='*.nfo')
        self.file._delete_junk_files(tmpdir, config)
        mock_send2trash.assert_not_called()

    @patch('picard.file.send2trash')
    def test_delete_junk_files_wildcard(self, mock_send2trash):
        """Wildcard *.url matches foo.url, bar.url."""
        tmpdir = self._create_junk_dir(['foo.url', 'bar.url', 'keep.mp3'])
        config = self._make_config(enabled=True, pattern='*.url')
        self.file._delete_junk_files(tmpdir, config)
        trashed_files = {os.path.basename(call[0][0]) for call in mock_send2trash.call_args_list}
        self.assertEqual(trashed_files, {'foo.url', 'bar.url'})

    @patch('picard.file.send2trash')
    def test_delete_junk_files_case_insensitive(self, mock_send2trash):
        """Pattern matching is case-insensitive."""
        tmpdir = self._create_junk_dir(['INFO.NFO', 'Playlist.M3U'])
        config = self._make_config(enabled=True, pattern='*.nfo *.m3u')
        self.file._delete_junk_files(tmpdir, config)
        trashed_files = {os.path.basename(call[0][0]) for call in mock_send2trash.call_args_list}
        self.assertEqual(trashed_files, {'INFO.NFO', 'Playlist.M3U'})


class EmptyDirUsesTrashTest(PicardTestCase):

    @patch('picard.util.emptydir.send2trash')
    def test_rm_empty_dir_uses_send2trash(self, mock_send2trash):
        """rm_empty_dir should use send2trash instead of shutil.rmtree."""
        from picard.util import emptydir
        tmpdir = self.mktmpdir(ignore_errors=True)
        emptydir.rm_empty_dir(tmpdir)
        mock_send2trash.assert_called_once_with(tmpdir)

    @patch('picard.util.emptydir.send2trash', None)
    @patch('picard.util.emptydir.shutil')
    def test_rm_empty_dir_fallback_to_rmtree(self, mock_shutil):
        """rm_empty_dir should fall back to shutil.rmtree if send2trash is None."""
        from picard.util import emptydir
        tmpdir = self.mktmpdir(ignore_errors=True)
        emptydir.rm_empty_dir(tmpdir)
        mock_shutil.rmtree.assert_called_once_with(tmpdir)
