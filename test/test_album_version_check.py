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
# along with this program; if not, see <https://www.gnu.org/licenses/>.

from unittest.mock import (
    Mock,
    patch,
)

from test.picardtestcase import PicardTestCase

from picard.album import Album
from picard.releasegroup import ReleaseGroup
from picard.track import Track


class AlbumVersionCheckTest(PicardTestCase):
    """Tests for Album._check_for_better_version and _evaluate_alternative_versions."""

    def setUp(self):
        super().setUp()
        self.album = Album('album-1')
        self.album.metadata['album'] = 'Test Album'
        self.release_group = ReleaseGroup('rg-1')
        self.album.release_group = self.release_group

    def _add_tracks(self, count):
        """Add the given number of tracks to the album."""
        for i in range(count):
            track = Track(f'track-{i}')
            self.album.tracks.append(track)

    def _add_files(self, count):
        """Simulate having the given number of files via _files_count."""
        self.album._files_count = count

    def _make_version(self, version_id, totaltracks, name='Some Version'):
        return {
            'id': version_id,
            'name': name,
            'totaltracks': totaltracks,
            'countries': [],
            'formats': [],
            'extra': '',
        }

    def test_check_skipped_when_complete(self):
        """When album is_complete(), no version check should happen."""
        self._add_tracks(3)
        self._add_files(3)
        # Make all tracks complete (each has a matched file)
        for track in self.album.tracks:
            file_mock = Mock()
            file_mock.state = Mock()
            track.files.append(file_mock)

        # Patch is_complete to return True
        with patch.object(self.album, 'is_complete', return_value=True):
            with patch.object(self.release_group, 'load_versions') as mock_load:
                self.album._check_for_better_version()
                mock_load.assert_not_called()

    def test_check_skipped_when_track_count_matches(self):
        """When file count == track count, no version check should happen."""
        self._add_tracks(10)
        self._add_files(10)

        with patch.object(self.release_group, 'load_versions') as mock_load:
            self.album._check_for_better_version()
            mock_load.assert_not_called()

    def test_check_skipped_when_no_files(self):
        """When no files are loaded, no version check should happen."""
        self._add_tracks(10)
        # _files_count defaults to 0, no unmatched files

        with patch.object(self.release_group, 'load_versions') as mock_load:
            self.album._check_for_better_version()
            mock_load.assert_not_called()

    def test_check_skipped_when_no_release_group(self):
        """When album has no release_group, no version check should happen."""
        self._add_tracks(10)
        self._add_files(8)
        self.album.release_group = None

        # Should not raise any error
        self.album._check_for_better_version()

    def test_check_triggered_on_mismatch(self):
        """When file count != track count, version check should be triggered."""
        self._add_tracks(12)
        self._add_files(10)

        with patch.object(self.release_group, 'load_versions') as mock_load:
            self.album._check_for_better_version()
            mock_load.assert_called_once()

    def test_check_uses_loaded_versions_directly(self):
        """When release_group.loaded is True, should use versions directly."""
        self._add_tracks(12)
        self._add_files(10)
        self.release_group.loaded = True
        self.release_group.versions = []

        with patch.object(self.release_group, 'load_versions') as mock_load:
            with patch.object(self.album, '_evaluate_alternative_versions') as mock_eval:
                self.album._check_for_better_version()
                mock_load.assert_not_called()
                mock_eval.assert_called_once()

    def test_better_version_found(self):
        """When a version with matching track count exists, notify via statusbar."""
        self._add_tracks(12)
        self._add_files(10)

        self.release_group.loaded = True
        self.release_group.versions = [
            self._make_version('album-1', 12, '12 tracks version'),  # current album
            self._make_version('album-2', 10, '10 tracks version'),  # better match
            self._make_version('album-3', 8, '8 tracks version'),  # no match
        ]

        self.album._check_for_better_version()

        self.tagger.window.set_statusbar_message.assert_called()
        call_args = self.tagger.window.set_statusbar_message.call_args
        # The second positional arg is the dict with album and version info
        msg_dict = call_args[0][1]
        self.assertEqual(msg_dict['album'], 'Test Album')
        self.assertEqual(msg_dict['version'], '10 tracks version')

    def test_no_better_version_found(self):
        """When no version has matching track count, no notification."""
        self._add_tracks(12)
        self._add_files(10)

        self.release_group.loaded = True
        self.release_group.versions = [
            self._make_version('album-1', 12, '12 tracks version'),
            self._make_version('album-3', 8, '8 tracks version'),
        ]

        # Reset mock to clear any previous calls (from album init)
        self.tagger.window.set_statusbar_message.reset_mock()

        self.album._check_for_better_version()

        self.tagger.window.set_statusbar_message.assert_not_called()

    def test_current_album_not_suggested(self):
        """A version with matching tracks but same ID as current album should not be suggested."""
        self._add_tracks(12)
        self._add_files(10)

        self.release_group.loaded = True
        self.release_group.versions = [
            self._make_version('album-1', 10, 'Same album, 10 tracks'),  # same ID as current
        ]

        self.tagger.window.set_statusbar_message.reset_mock()

        self.album._check_for_better_version()

        self.tagger.window.set_statusbar_message.assert_not_called()

    def test_evaluate_with_no_versions(self):
        """_evaluate_alternative_versions with empty versions should not crash."""
        self.release_group.versions = []
        self.album._evaluate_alternative_versions()  # Should not raise

    def test_evaluate_with_no_release_group(self):
        """_evaluate_alternative_versions with no release_group should not crash."""
        self.album.release_group = None
        self.album._evaluate_alternative_versions()  # Should not raise
