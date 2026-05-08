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
    MagicMock,
    Mock,
    patch,
)

from test.picardtestcase import PicardTestCase

from picard.album import Album
from picard.album_requests import TaskType
from picard.cluster import Cluster
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


class AutoSaveConfigurableDelayTest(PicardTestCase):
    """Tests for configurable auto-save delay."""

    def setUp(self):
        super().setUp()
        self.album = Album('test-album-id')
        self.album.loaded = True

    def _make_perfect_album(self):
        track = Track('track-1')
        file = Mock(spec=File)
        file.is_saved.return_value = False
        file.state = File.State.NORMAL
        track.files.append(file)
        self.album.tracks = [track]
        self.album.unmatched_files = Mock()
        self.album.unmatched_files.files = []
        self.album.metadata.images.append(Mock())

    def test_delay_uses_config_value(self):
        """Auto-save timer should use auto_save_delay_seconds from config."""
        self._make_perfect_album()
        self.set_config_values(setting={
            'auto_save_perfect_albums': True,
            'auto_save_delay_seconds': 7,
        })
        with patch('picard.album.QtCore.QTimer') as mock_timer:
            self.album._check_auto_save()
            mock_timer.singleShot.assert_called_once()
            delay_ms = mock_timer.singleShot.call_args[0][0]
            self.assertEqual(delay_ms, 7000)

    def test_delay_default_5_seconds(self):
        """Default delay should be 5 seconds (5000ms)."""
        self._make_perfect_album()
        self.set_config_values(setting={
            'auto_save_perfect_albums': True,
            'auto_save_delay_seconds': 5,
        })
        with patch('picard.album.QtCore.QTimer') as mock_timer:
            self.album._check_auto_save()
            delay_ms = mock_timer.singleShot.call_args[0][0]
            self.assertEqual(delay_ms, 5000)


class CoverArtCompleteCallbackTest(PicardTestCase):
    """Tests for the cover art completion callback triggering auto-save."""

    def setUp(self):
        super().setUp()
        self.album = Album('test-album-id')
        self.album.loaded = True

    def _make_perfect_album(self):
        track = Track('track-1')
        file = Mock(spec=File)
        file.is_saved.return_value = False
        file.state = File.State.NORMAL
        track.files.append(file)
        self.album.tracks = [track]
        self.album.unmatched_files = Mock()
        self.album.unmatched_files.files = []
        self.album.metadata.images.append(Mock())

    def test_on_cover_art_complete_triggers_auto_save(self):
        """_on_cover_art_complete should call _check_auto_save."""
        self._make_perfect_album()
        self.set_config_values(setting={
            'auto_save_perfect_albums': True,
            'auto_save_delay_seconds': 5,
        })
        with patch('picard.album.QtCore.QTimer') as mock_timer:
            self.album._on_cover_art_complete()
            mock_timer.singleShot.assert_called_once()
            self.assertTrue(self.album._auto_save_scheduled)

    def test_on_cover_art_complete_not_perfect(self):
        """_on_cover_art_complete should not schedule if album is not perfect."""
        self.set_config_values(setting={
            'auto_save_perfect_albums': True,
            'auto_save_delay_seconds': 5,
        })
        with patch('picard.album.QtCore.QTimer') as mock_timer:
            self.album._on_cover_art_complete()
            mock_timer.singleShot.assert_not_called()


class AddFileTriggerTest(PicardTestCase):
    """Tests for auto-save triggering when a file is matched to a track."""

    def setUp(self):
        super().setUp()
        self.album = Album('test-album-id')
        self.album.loaded = True
        self.tagger.window = Mock()

    def test_add_file_triggers_auto_save_check(self):
        """album.add_file should call _check_auto_save when new_album=True."""
        track = Track('track-1')
        file = Mock(spec=File)
        file.is_saved.return_value = False
        file.state = File.State.NORMAL
        track.files.append(file)
        self.album.tracks = [track]
        self.album.unmatched_files = Mock()
        self.album.unmatched_files.files = []
        self.album.metadata.images.append(Mock())
        self.album.ui_item = Mock()

        self.set_config_values(setting={
            'auto_save_perfect_albums': True,
            'auto_save_delay_seconds': 5,
        })

        with patch.object(self.album, '_check_auto_save') as mock_check:
            new_file = Mock(spec=File)
            new_file.metadata = Mock()
            new_file.orig_metadata = Mock()
            new_file.orig_metadata.images = []
            new_file.metadata.images = []
            self.album.add_file(track, new_file, new_album=True)
            mock_check.assert_called_once()

    def test_add_file_no_trigger_when_not_new_album(self):
        """album.add_file with new_album=False should not call _check_auto_save."""
        track = Track('track-1')
        self.album.tracks = [track]
        self.album.unmatched_files = Mock()
        self.album.unmatched_files.files = []

        self.set_config_values(setting={
            'auto_save_perfect_albums': True,
            'auto_save_delay_seconds': 5,
        })

        with patch.object(self.album, '_check_auto_save') as mock_check:
            file = Mock(spec=File)
            self.album.add_file(track, file, new_album=False)
            mock_check.assert_not_called()


class ReloadCoverArtTest(PicardTestCase):
    """Tests for Album.reload_cover_art method."""

    def setUp(self):
        super().setUp()
        self.album = Album('test-album-id')
        self.album.loaded = True
        self.tagger.window = Mock()
        self.album.metadata['album'] = 'Test Album'

    def test_reload_cover_art_calls_processors(self):
        """reload_cover_art should call run_album_metadata_processors with cached release data."""
        self.album._release_node_cache = {'id': 'test-release', 'media': []}
        with patch('picard.album.run_album_metadata_processors') as mock_proc:
            self.album.reload_cover_art()
            mock_proc.assert_called_once_with(
                self.album, self.album.metadata, self.album._release_node_cache)

    def test_reload_cover_art_no_cache(self):
        """reload_cover_art should do nothing if no cached release data."""
        with patch('picard.album.run_album_metadata_processors') as mock_proc:
            self.album.reload_cover_art()
            mock_proc.assert_not_called()

    def test_reload_cover_art_not_loaded(self):
        """reload_cover_art should do nothing if album not loaded."""
        self.album.loaded = False
        self.album._release_node_cache = {'id': 'test-release'}
        with patch('picard.album.run_album_metadata_processors') as mock_proc:
            self.album.reload_cover_art()
            mock_proc.assert_not_called()


class AutoSaveWorkflowTest(PicardTestCase):
    """End-to-end workflow tests simulating realistic scenarios."""

    def setUp(self):
        super().setUp()
        self.album = Album('test-album-id')
        self.album.loaded = True
        self.tagger.window = Mock()
        self.set_config_values(setting={
            'auto_save_perfect_albums': True,
            'auto_save_delay_seconds': 5,
            'auto_remove_saved_albums': True,
        })

    def _make_track_with_file(self, track_id='track-1', saved=False):
        track = Track(track_id)
        file = Mock(spec=File)
        file.is_saved.return_value = saved
        file.state = File.State.NORMAL
        track.files.append(file)
        return track, file

    def _setup_album(self, num_tracks=1, with_images=True, with_unmatched=False):
        """Set up an album with the given number of matched tracks."""
        tracks = []
        files = []
        for i in range(num_tracks):
            track, file = self._make_track_with_file(f'track-{i}')
            tracks.append(track)
            files.append(file)
        self.album.tracks = tracks
        self.album.unmatched_files = Mock()
        if with_unmatched:
            unmatched_file = Mock(spec=File)
            self.album.unmatched_files.files = [unmatched_file]
        else:
            self.album.unmatched_files.files = []
        if with_images:
            self.album.metadata.images.append(Mock())
        self.album.metadata['album'] = 'Test Album'
        self.album.metadata['albumartist'] = 'Test Artist'
        return tracks, files

    def test_workflow_perfect_album_first_load(self):
        """Scenario: Album loads, files match, covers load → auto-save triggers.

        Simulates: tags loaded → files matched → cover art downloads complete →
        _on_cover_art_complete fires → auto-save scheduled.
        """
        tracks, files = self._setup_album(num_tracks=3, with_images=True)

        with patch('picard.album.QtCore.QTimer') as mock_timer:
            self.album._on_cover_art_complete()
            mock_timer.singleShot.assert_called_once()
            delay_ms = mock_timer.singleShot.call_args[0][0]
            self.assertEqual(delay_ms, 5000)
            self.assertTrue(self.album._auto_save_scheduled)

    def test_workflow_no_cover_art_no_auto_save(self):
        """Scenario: Album loads perfectly for tags but no cover art found.

        Should NOT auto-save because is_perfect() requires images.
        """
        self._setup_album(num_tracks=2, with_images=False)

        with patch('picard.album.QtCore.QTimer') as mock_timer:
            self.album._on_cover_art_complete()
            mock_timer.singleShot.assert_not_called()
            self.assertFalse(self.album._auto_save_scheduled)

    def test_workflow_unmatched_files_block_auto_save(self):
        """Scenario: Album has cover art but some files aren't matched.

        Should NOT auto-save because is_complete() fails with unmatched files.
        """
        self._setup_album(num_tracks=1, with_images=True, with_unmatched=True)

        with patch('picard.album.QtCore.QTimer') as mock_timer:
            self.album._on_cover_art_complete()
            mock_timer.singleShot.assert_not_called()

    def test_workflow_pending_tasks_block_auto_save(self):
        """Scenario: Album is complete with images but cover art still downloading.

        Should NOT auto-save while optional tasks are pending.
        """
        self._setup_album(num_tracks=1, with_images=True)
        self.album.add_task('coverart_123', TaskType.OPTIONAL, 'Downloading cover art')

        with patch('picard.album.QtCore.QTimer') as mock_timer:
            self.album._check_auto_save()
            mock_timer.singleShot.assert_not_called()

    def test_workflow_task_completes_then_cover_art_complete(self):
        """Scenario: Last optional task completes, then cover art callback fires.

        The complete_task call alone may not find a perfect state (timing issue),
        but _on_cover_art_complete should trigger auto-save.
        """
        self._setup_album(num_tracks=1, with_images=True)
        self.album.add_task('coverart_processing_123', TaskType.OPTIONAL, 'Processing')

        with patch('picard.album.QtCore.QTimer') as mock_timer:
            self.album.complete_task('coverart_processing_123')
            # complete_task calls _check_auto_save, album should be perfect now
            self.assertTrue(mock_timer.singleShot.called)

    def test_workflow_auto_save_execute_then_remove(self):
        """Scenario: Full flow from perfect album to save to finish.

        Auto-save executes → files are saved → _auto_save_finish is called.
        """
        tracks, files = self._setup_album(num_tracks=2, with_images=True)
        self.album._auto_save_scheduled = True
        self.tagger._auto_save_queue = [self.album]
        self.tagger._auto_save_running = False

        self.album._auto_save_execute()

        for f in files:
            f.save.assert_called_once()
        self.assertTrue(self.tagger._auto_save_running)

    def test_workflow_auto_save_cancelled_by_state_change(self):
        """Scenario: Album becomes perfect, auto-save scheduled, then user
        removes a file before the timer fires → auto-save cancelled.
        """
        tracks, files = self._setup_album(num_tracks=1, with_images=True)
        self.album._auto_save_scheduled = True

        # Simulate user removing the matched file before timer fires
        files[0].is_saved.return_value = True  # No longer modified

        self.album._auto_save_execute()
        files[0].save.assert_not_called()
        self.assertFalse(self.album._auto_save_scheduled)

    def test_workflow_setting_disabled_blocks_everything(self):
        """Scenario: Auto-save setting is off. Nothing should happen regardless of state."""
        self._setup_album(num_tracks=1, with_images=True)
        self.set_config_values(setting={'auto_save_perfect_albums': False})

        with patch('picard.album.QtCore.QTimer') as mock_timer:
            self.album._on_cover_art_complete()
            self.album._check_auto_save()
            mock_timer.singleShot.assert_not_called()

    def test_workflow_idempotent_triggers(self):
        """Scenario: Multiple triggers fire (cover art complete + add_file + complete_task).

        Auto-save should only be scheduled once thanks to _auto_save_scheduled flag.
        """
        self._setup_album(num_tracks=1, with_images=True)

        with patch('picard.album.QtCore.QTimer') as mock_timer:
            self.album._on_cover_art_complete()
            self.album._check_auto_save()
            self.album._check_auto_save()
            self.assertEqual(mock_timer.singleShot.call_count, 1)

    def test_workflow_reload_cover_art_then_auto_save(self):
        """Scenario: User clicks 'Reload Cover Art', covers load, auto-save triggers.

        Simulates: reload_cover_art → providers run → _on_cover_art_complete → auto-save.
        """
        self._setup_album(num_tracks=1, with_images=False)
        self.album._release_node_cache = {'id': 'test-release', 'media': []}

        with patch('picard.album.run_album_metadata_processors'):
            self.album.reload_cover_art()

        # Simulate cover art arriving after reload
        self.album.metadata.images.append(Mock())

        with patch('picard.album.QtCore.QTimer') as mock_timer:
            self.album._on_cover_art_complete()
            mock_timer.singleShot.assert_called_once()

    def test_workflow_multi_track_partial_match(self):
        """Scenario: 3-track album but only 2 tracks have files.

        Should NOT auto-save because not all tracks are complete.
        """
        track1, _ = self._make_track_with_file('track-1')
        track2, _ = self._make_track_with_file('track-2')
        track3 = Track('track-3')  # No file matched
        self.album.tracks = [track1, track2, track3]
        self.album.unmatched_files = Mock()
        self.album.unmatched_files.files = []
        self.album.metadata.images.append(Mock())

        with patch('picard.album.QtCore.QTimer') as mock_timer:
            self.album._on_cover_art_complete()
            mock_timer.singleShot.assert_not_called()


class AutoSaveSerializationTest(PicardTestCase):
    """Tests for serialized auto-save (one album at a time)."""

    def setUp(self):
        super().setUp()
        self.tagger.window = Mock()
        self.set_config_values(setting={
            'auto_save_perfect_albums': True,
            'auto_save_delay_seconds': 5,
            'auto_remove_saved_albums': False,
        })

    def _make_perfect_album(self, album_id):
        album = Album(album_id)
        album.loaded = True
        album.metadata['album'] = f'Album {album_id}'
        album.metadata['albumartist'] = 'Artist'
        track = Track(f'track-{album_id}')
        file = Mock(spec=File)
        file.is_saved.return_value = False
        file.state = File.State.NORMAL
        track.files.append(file)
        album.tracks = [track]
        album.unmatched_files = Mock()
        album.unmatched_files.files = []
        album.metadata.images.append(Mock())
        album._auto_save_scheduled = True
        return album, file

    def test_second_album_waits_for_first(self):
        """When two albums enqueue, only the first starts saving."""
        album_a, file_a = self._make_perfect_album('album-a')
        album_b, file_b = self._make_perfect_album('album-b')

        with patch('picard.album.QtCore.QTimer'):
            album_a._auto_save_enqueue()
            album_b._auto_save_enqueue()

        self.assertTrue(self.tagger._auto_save_running)
        file_a.save.assert_called_once()
        file_b.save.assert_not_called()

    def test_second_album_starts_after_first_finishes(self):
        """After first album finishes, second starts."""
        album_a, file_a = self._make_perfect_album('album-a')
        album_b, file_b = self._make_perfect_album('album-b')

        with patch('picard.album.QtCore.QTimer') as mock_timer:
            album_a._auto_save_enqueue()
            album_b._auto_save_enqueue()

            file_a.save.assert_called_once()
            file_b.save.assert_not_called()

            # Simulate all files of album A saved
            album_a._auto_save_finish()

            self.assertFalse(self.tagger._auto_save_running)
            self.assertIn(album_b, self.tagger._auto_save_queue)

    def test_queue_order_preserved(self):
        """Albums are processed in FIFO order."""
        albums = []
        for i in range(3):
            album, _ = self._make_perfect_album(f'album-{i}')
            albums.append(album)

        with patch('picard.album.QtCore.QTimer'):
            for album in albums:
                album._auto_save_enqueue()

        self.assertEqual(self.tagger._auto_save_queue[0], albums[0])

    def test_cancelled_album_removed_from_queue(self):
        """If album is no longer perfect when its turn comes, skip it."""
        album_a, file_a = self._make_perfect_album('album-a')
        album_b, file_b = self._make_perfect_album('album-b')

        with patch('picard.album.QtCore.QTimer'):
            album_a._auto_save_enqueue()
            album_b._auto_save_enqueue()

            album_a._auto_save_finish()

            self.assertNotIn(album_a, self.tagger._auto_save_queue)
            self.assertIn(album_b, self.tagger._auto_save_queue)

    def test_edition_change_cancels_auto_save(self):
        """Edition change resets _auto_save_scheduled and removes from queue."""
        album, file = self._make_perfect_album('album-switch')

        with patch('picard.album.QtCore.QTimer'):
            album._auto_save_enqueue()
            self.assertIn(album, self.tagger._auto_save_queue)

            # Simulate what switch_release_version does
            album._auto_save_scheduled = False
            self.tagger._auto_save_queue.remove(album)

            # Now the timer fires but enqueue is skipped
            album._auto_save_enqueue()
            self.assertNotIn(album, self.tagger._auto_save_queue)

    def test_enqueue_skipped_if_cancelled(self):
        """_auto_save_enqueue should skip if _auto_save_scheduled was reset."""
        album, _ = self._make_perfect_album('album-skip')
        album._auto_save_scheduled = False  # Simulate cancellation

        with patch('picard.album.QtCore.QTimer'):
            album._auto_save_enqueue()

        self.assertFalse(hasattr(self.tagger, '_auto_save_queue') and
                         album in self.tagger._auto_save_queue)
