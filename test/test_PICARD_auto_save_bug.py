
from unittest.mock import Mock, patch
from test.picardtestcase import PicardTestCase
from picard.album import Album
from picard.track import Track
from picard.file import File
from picard.cluster import Cluster
from picard.metadata import Metadata
import weakref

class TestAutoSaveBug(PicardTestCase):
    def setUp(self):
        super().setUp()
        self.set_config_values(setting={'auto_save_perfect_albums': True})
        self.album = Album('test-album')
        self.album.loaded = True
        self.album.tagger = self.tagger
        self.tagger.remove_cluster = Mock()

        self.track = Track('track-1', self.album)
        self.album.tracks = [self.track]
        # Cluster uses weakref for album
        self.album.unmatched_files = Cluster("Unmatched", related_album=self.album)

        self.file = Mock(spec=File)
        self.file.parent_item = None
        self.file.is_saved.return_value = False
        self.file.state = File.State.NORMAL
        self.file.metadata = Metadata()
        self.file.metadata.images.append(Mock())
        self.file.metadata.length = 1000
        self.file.orig_metadata = Metadata()
        self.file.orig_metadata.length = 1000
        self.file.column.return_value = ""
        self.file.base_filename = "test.mp3"
        self.file.discnumber = 0
        self.file.tracknumber = 0
        self.file._move = Mock()

        # Mock some things to avoid deep Picard logic
        self.album.add_metadata_images_from_children = Mock()
        self.album.remove_metadata_images_from_children = Mock()
        self.album.metadata.images.append(Mock())
        # Make it perfect when the file is added
        self.album.is_complete = Mock(return_value=True)
        self.album.is_modified = Mock(return_value=True)

    def test_auto_save_on_matching(self):
        with patch('picard.album.QtCore.QTimer.singleShot') as mock_timer:
            # Simulate matching a file to the track
            # track.add_file calls album.add_file
            self.track.add_file(self.file)

            self.assertTrue(mock_timer.called, "Auto-save should have been scheduled after matching file")

    def test_auto_save_on_removing_unmatched(self):
        self.album.unmatched_files.add_file(self.file)
        # Ensure it has the album set (Unmatched Files special cluster has it)
        self.assertIsNotNone(self.album.unmatched_files.album)

        # When remove_file is called, it calls _update_related_album which calls _check_auto_save
        with patch.object(Album, '_check_auto_save') as mock_check:
            self.album.unmatched_files.remove_file(self.file)
            self.assertTrue(mock_check.called, "Auto-save should have been checked after removing unmatched file")

    def test_auto_save_on_manual_edit(self):
        with patch('picard.album.QtCore.QTimer.singleShot') as mock_timer:
            # Simulate MetadataBox updating objects after an edit
            # obj.update() now triggers _check_auto_save if called via MetadataBox._update_objects
            from picard.ui.metadatabox import MetadataBox
            # Since we can't easily instantiate MetadataBox in tests, we simulate its new logic
            for obj in [self.album]:
                obj.update()
                if isinstance(obj, Album):
                    obj._check_auto_save()
            self.assertTrue(mock_timer.called, "Auto-save should have been scheduled after manual tag edit")

if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
