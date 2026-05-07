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
from picard.album_requests import TaskType
from picard.file import File
from picard.track import Track


class IsPerfectTest(PicardTestCase):
    """Tests for Album.is_perfect() method."""

    def setUp(self):
        super().setUp()
        self.album = Album('test-album-id')
        self.album.loaded = True

    def _make_perfect_album(self):
        """Set up album in a perfect state: complete, modified, with images, no tasks."""
        track = Track('track-1')
        file = Mock(spec=File)
        file.is_saved.return_value = False
        file.state = File.State.NORMAL
        track.files.append(file)
        # num_linked_files is a property = len(track.files), already 1
        self.album.tracks = [track]
        self.album.unmatched_files = Mock()
        self.album.unmatched_files.files = []
        self.album.metadata.images.append(Mock())
        return track, file

    def test_is_perfect_all_conditions_met(self):
        self._make_perfect_album()
        self.assertTrue(self.album.is_perfect())

    def test_is_perfect_not_loaded(self):
        self._make_perfect_album()
        self.album.loaded = False
        self.assertFalse(self.album.is_perfect())

    def test_is_perfect_not_complete(self):
        """Album with no tracks is not complete, hence not perfect."""
        self.album.metadata.images.append(Mock())
        self.assertFalse(self.album.is_perfect())

    def test_is_perfect_not_modified(self):
        """Album where all files are saved is not modified, hence not perfect."""
        track = Track('track-1')
        file = Mock(spec=File)
        file.is_saved.return_value = True  # Already saved
        file.state = File.State.NORMAL
        track.files.append(file)
        # num_linked_files is a property = len(track.files), already 1
        self.album.tracks = [track]
        self.album.unmatched_files = Mock()
        self.album.unmatched_files.files = []
        self.album.metadata.images.append(Mock())
        self.assertFalse(self.album.is_perfect())

    def test_is_perfect_no_images(self):
        """Album with no cover art is not perfect."""
        track = Track('track-1')
        file = Mock(spec=File)
        file.is_saved.return_value = False
        file.state = File.State.NORMAL
        track.files.append(file)
        # num_linked_files is a property = len(track.files), already 1
        self.album.tracks = [track]
        self.album.unmatched_files = Mock()
        self.album.unmatched_files.files = []
        # No images added
        self.assertFalse(self.album.is_perfect())

    def test_is_perfect_has_critical_tasks(self):
        self._make_perfect_album()
        self.album.add_task('critical-task', TaskType.CRITICAL, 'Loading metadata')
        self.assertFalse(self.album.is_perfect())

    def test_is_perfect_has_optional_tasks(self):
        self._make_perfect_album()
        self.album.add_task('cover-art', TaskType.OPTIONAL, 'Downloading cover art')
        self.assertFalse(self.album.is_perfect())

    def test_is_perfect_has_plugin_tasks(self):
        self._make_perfect_album()
        self.album.add_task('plugin-task', TaskType.PLUGIN, 'Plugin processing')
        self.assertFalse(self.album.is_perfect())


class HasPendingOptionalTasksTest(PicardTestCase):
    """Tests for Album._has_pending_optional_tasks() method."""

    def setUp(self):
        super().setUp()
        self.album = Album('test-album-id')

    def test_no_tasks(self):
        self.assertFalse(self.album._has_pending_optional_tasks())

    def test_only_critical_tasks(self):
        self.album.add_task('critical', TaskType.CRITICAL, 'Critical task')
        self.assertFalse(self.album._has_pending_optional_tasks())

    def test_optional_task(self):
        self.album.add_task('optional', TaskType.OPTIONAL, 'Optional task')
        self.assertTrue(self.album._has_pending_optional_tasks())

    def test_plugin_task(self):
        self.album.add_task('plugin', TaskType.PLUGIN, 'Plugin task')
        self.assertTrue(self.album._has_pending_optional_tasks())


class CheckAutoSaveTest(PicardTestCase):
    """Tests for Album._check_auto_save() method."""

    def setUp(self):
        super().setUp()
        self.album = Album('test-album-id')
        self.album.loaded = True

    def _make_perfect_album(self):
        """Set up album in a perfect state."""
        track = Track('track-1')
        file = Mock(spec=File)
        file.is_saved.return_value = False
        file.state = File.State.NORMAL
        track.files.append(file)
        # num_linked_files is a property = len(track.files), already 1
        self.album.tracks = [track]
        self.album.unmatched_files = Mock()
        self.album.unmatched_files.files = []
        self.album.metadata.images.append(Mock())
        return track, file

    def test_auto_save_disabled(self):
        """Auto-save should not trigger when setting is disabled."""
        self._make_perfect_album()
        self.set_config_values(setting={'auto_save_perfect_albums': False})
        with patch('picard.album.QtCore.QTimer') as mock_timer:
            self.album._check_auto_save()
            mock_timer.singleShot.assert_not_called()

    def test_auto_save_enabled_not_perfect(self):
        """Auto-save should not trigger when album is not perfect."""
        self.set_config_values(setting={'auto_save_perfect_albums': True})
        # Album has no tracks, not complete
        with patch('picard.album.QtCore.QTimer') as mock_timer:
            self.album._check_auto_save()
            mock_timer.singleShot.assert_not_called()

    def test_auto_save_enabled_perfect(self):
        """Auto-save should schedule a timer when album is perfect."""
        self._make_perfect_album()
        self.set_config_values(setting={'auto_save_perfect_albums': True})
        with patch('picard.album.QtCore.QTimer') as mock_timer:
            self.album._check_auto_save()
            mock_timer.singleShot.assert_called_once()
            self.assertTrue(self.album._auto_save_scheduled)

    def test_auto_save_not_scheduled_twice(self):
        """Auto-save should not schedule twice if already scheduled."""
        self._make_perfect_album()
        self.set_config_values(setting={'auto_save_perfect_albums': True})
        with patch('picard.album.QtCore.QTimer') as mock_timer:
            self.album._check_auto_save()
            self.album._check_auto_save()
            # Should only be called once
            self.assertEqual(mock_timer.singleShot.call_count, 1)


class AutoSaveExecuteTest(PicardTestCase):
    """Tests for Album._auto_save_execute() method."""

    def setUp(self):
        super().setUp()
        self.album = Album('test-album-id')
        self.album.loaded = True
        self.tagger.window = Mock()

    def _make_perfect_album(self):
        """Set up album in a perfect state."""
        track = Track('track-1')
        file = Mock(spec=File)
        file.is_saved.return_value = False
        file.state = File.State.NORMAL
        track.files.append(file)
        # num_linked_files is a property = len(track.files), already 1
        self.album.tracks = [track]
        self.album.unmatched_files = Mock()
        self.album.unmatched_files.files = []
        self.album.metadata.images.append(Mock())
        self.album.metadata['album'] = 'Test Album'
        self.album.metadata['albumartist'] = 'Test Artist'
        return track, file

    def test_auto_save_execute_saves_files(self):
        """Auto-save should call file.save() for each correctly matched track."""
        track, file = self._make_perfect_album()
        self.album._auto_save_scheduled = True
        self.album._auto_save_execute()
        file.save.assert_called_once()
        self.assertFalse(self.album._auto_save_scheduled)

    def test_auto_save_cancelled_if_state_changes(self):
        """Auto-save should be cancelled if album is no longer perfect."""
        track, file = self._make_perfect_album()
        self.album._auto_save_scheduled = True
        # Make it no longer perfect by marking file as saved
        file.is_saved.return_value = True
        self.album._auto_save_execute()
        file.save.assert_not_called()
        self.assertFalse(self.album._auto_save_scheduled)

    def test_auto_save_execute_multiple_tracks(self):
        """Auto-save should save all correctly matched tracks."""
        self._make_perfect_album()

        track2 = Track('track-2')
        file2 = Mock(spec=File)
        file2.is_saved.return_value = False
        file2.state = File.State.NORMAL
        track2.files.append(file2)
        # num_linked_files is a property = len(track.files), already 1
        self.album.tracks.append(track2)

        self.album._auto_save_scheduled = True
        self.album._auto_save_execute()

        # Both files should be saved
        self.album.tracks[0].files[0].save.assert_called_once()
        file2.save.assert_called_once()

    def test_auto_save_shows_statusbar_message(self):
        """Auto-save should display a statusbar message."""
        self._make_perfect_album()
        self.album._auto_save_scheduled = True
        self.album._auto_save_execute()
        self.tagger.window.set_statusbar_message.assert_called_once()
