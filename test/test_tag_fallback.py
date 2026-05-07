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

"""Tests for the multi-source tag fallback flow:
   MB → Discogs → iTunes
"""

import json
from unittest.mock import (
    Mock,
    patch,
)

from test.picardtestcase import PicardTestCase

from picard.cluster import Cluster
from picard.file import File
from picard.metadata import Metadata


class DiscogsTagFallbackTest(PicardTestCase):
    """Tests for Discogs tag fallback when MB finds no match."""

    def setUp(self):
        super().setUp()
        self.set_config_values(setting={
            'discogs_match_threshold': 0.5,
            'discogs_enabled': True,
            'discogs_token': 'test_token',
        })
        self.cluster = Cluster("Test Album", artist="Test Artist")
        self.cluster._lookup_task = None
        self.tagger.window = Mock()
        self.tagger.discogs_api = Mock()
        self.tagger.remove_cluster = Mock()

        # Add mock files with durations matching Discogs tracklist (3:20, 4:10, 3:45)
        durations = [200000, 250000, 225000]
        for i in range(3):
            file = Mock(spec=File)
            file.metadata = Metadata()
            file.metadata['title'] = f'Track {i + 1}'
            file.metadata.length = durations[i]
            file.parent_item = None
            file.state = File.State.NORMAL
            file.base_filename = f'track{i + 1}.mp3'
            file.discnumber = 0
            file.tracknumber = i
            file._move = Mock()
            file.update = Mock()
            self.cluster.files.append(file)

    def _make_discogs_release(self):
        return {
            'id': 12345,
            'title': 'Test Album',
            'artists': [{'name': 'Test Artist'}],
            'artists_sort': 'Test Artist',
            'year': 2020,
            'genres': ['Rock'],
            'styles': ['Alternative Rock'],
            'labels': [{'name': 'Test Label'}],
            'tracklist': [
                {'type_': 'track', 'title': 'Track One', 'position': '1', 'duration': '3:20'},
                {'type_': 'track', 'title': 'Track Two', 'position': '2', 'duration': '4:10'},
                {'type_': 'track', 'title': 'Track Three', 'position': '3', 'duration': '3:45'},
            ],
            'images': [
                {'type': 'primary', 'width': 600, 'resource_url': 'http://img/cover.jpg'},
            ],
        }

    def test_discogs_fallback_applies_tags(self):
        """When MB finds nothing but Discogs has a good match, tags are applied."""
        self.cluster._discogs_candidates = [self._make_discogs_release()]

        result = self.cluster._try_discogs_tag_fallback()

        self.assertTrue(result)
        for file in self.cluster.files:
            self.assertEqual(file.metadata['albumartist'], 'Test Artist')
            self.assertEqual(file.metadata['album'], 'Test Album')
            self.assertEqual(file.metadata['date'], '2020')
            self.assertEqual(file.metadata['genre'], 'Rock; Alternative Rock')
            self.assertEqual(file.metadata['label'], 'Test Label')
            self.assertEqual(file.metadata['totaltracks'], '3')
            file.update.assert_called()

    def test_discogs_fallback_applies_track_titles(self):
        """Discogs tracklist should set individual track titles."""
        self.cluster._discogs_candidates = [self._make_discogs_release()]
        self.cluster._try_discogs_tag_fallback()

        self.assertEqual(self.cluster.files[0].metadata['title'], 'Track One')
        self.assertEqual(self.cluster.files[1].metadata['title'], 'Track Two')
        self.assertEqual(self.cluster.files[2].metadata['title'], 'Track Three')

    def test_discogs_fallback_no_candidates(self):
        """Should return False when no Discogs candidates available."""
        self.cluster._discogs_candidates = []
        self.assertFalse(self.cluster._try_discogs_tag_fallback())

    def test_discogs_fallback_below_threshold(self):
        """Should return False when Discogs match score is below threshold."""
        self.set_config_values(setting={'discogs_match_threshold': 0.99})
        release = self._make_discogs_release()
        release['tracklist'] = []  # Empty tracklist = low score
        self.cluster._discogs_candidates = [release]
        self.assertFalse(self.cluster._try_discogs_tag_fallback())

    def test_discogs_fallback_stores_cover_cache(self):
        """Discogs fallback should cache release data for cover art provider."""
        release = self._make_discogs_release()
        self.cluster._discogs_candidates = [release]
        self.cluster._try_discogs_tag_fallback()

        self.assertTrue(hasattr(self.tagger, '_discogs_release_cache'))
        self.assertIn(12345, self.tagger._discogs_release_cache)


class ITunesTagFallbackTest(PicardTestCase):
    """Tests for iTunes tag fallback."""

    def setUp(self):
        super().setUp()
        self.cluster = Cluster("OK Computer", artist="Radiohead")
        self.cluster._lookup_task = None
        self.tagger.window = Mock()
        self.tagger.discogs_api = Mock()
        self.tagger.remove_cluster = Mock()

        for i in range(3):
            file = Mock(spec=File)
            file.metadata = Metadata()
            file.metadata['title'] = f'Track {i + 1}'
            file.metadata.length = 200000
            file.parent_item = None
            file.state = File.State.NORMAL
            file.base_filename = f'track{i + 1}.mp3'
            file.discnumber = 0
            file.tracknumber = i
            file._move = Mock()
            file.update = Mock()
            self.cluster.files.append(file)

    def test_itunes_fallback_sends_request(self):
        """_try_itunes_tag_fallback should call webservice.download_url."""
        self.cluster._try_itunes_tag_fallback()
        self.tagger.webservice.download_url.assert_called_once()
        call_kwargs = self.tagger.webservice.download_url.call_args
        url = str(call_kwargs.kwargs.get('url', call_kwargs[1].get('url', '')))
        self.assertIn('itunes.apple.com', url)

    def test_itunes_fallback_applies_tags(self):
        """iTunes response should set tags on cluster files."""
        response = json.dumps({
            'results': [{
                'artistName': 'Radiohead',
                'collectionName': 'OK Computer',
                'releaseDate': '1997-06-16T07:00:00Z',
                'primaryGenreName': 'Alternative',
                'trackCount': 12,
            }]
        }).encode('utf-8')

        self.cluster._itunes_lookup_finished(
            'Radiohead', 'OK Computer', response, Mock(), None)

        for file in self.cluster.files:
            self.assertEqual(file.metadata['albumartist'], 'Radiohead')
            self.assertEqual(file.metadata['album'], 'OK Computer')
            self.assertEqual(file.metadata['date'], '1997')
            self.assertEqual(file.metadata['genre'], 'Alternative')
            self.assertEqual(file.metadata['totaltracks'], '12')
            file.update.assert_called()

    def test_itunes_fallback_no_match(self):
        """Should display 'no match' message when iTunes returns no similar results."""
        response = json.dumps({
            'results': [{
                'artistName': 'Completely Different',
                'collectionName': 'Wrong Album',
                'releaseDate': '2020-01-01',
                'primaryGenreName': 'Pop',
                'trackCount': 5,
            }]
        }).encode('utf-8')

        self.cluster._itunes_lookup_finished(
            'Radiohead', 'OK Computer', response, Mock(), None)

        # Tags should NOT be applied
        self.assertNotEqual(self.cluster.files[0].metadata.get('albumartist', ''), 'Completely Different')

    def test_itunes_fallback_error(self):
        """Should handle errors gracefully."""
        self.cluster._itunes_lookup_finished(
            'Radiohead', 'OK Computer', None, Mock(), 'Network error')
        # Should not crash


class LookupFlowTest(PicardTestCase):
    """Integration tests for the full lookup flow: MB → Discogs → iTunes."""

    def setUp(self):
        super().setUp()
        self.set_config_values(setting={
            'discogs_enabled': True,
            'discogs_token': 'test_token',
            'discogs_match_threshold': 0.5,
            'cluster_lookup_threshold': 0.0,
        })
        self.cluster = Cluster("Test Album", artist="Test Artist")
        self.cluster._lookup_task = None
        self.tagger.window = Mock()
        self.tagger.discogs_api = Mock()
        self.tagger.remove_cluster = Mock()

        file = Mock(spec=File)
        file.metadata = Metadata()
        file.metadata['title'] = 'Track 1'
        file.metadata.length = 200000
        file.parent_item = None
        file.state = File.State.NORMAL
        file.base_filename = 'track1.mp3'
        file.discnumber = 0
        file.tracknumber = 0
        file._move = Mock()
        file.update = Mock()
        self.cluster.files.append(file)
        self.tagger.move_files_to_album = Mock()

    def test_mb_match_found_skips_fallbacks(self):
        """When MB finds a match, Discogs/iTunes fallbacks are not used."""
        document = {
            'releases': [{
                'id': 'mb-release-id',
                'title': 'Test Album',
                'artist-credit': [{'name': 'Test Artist', 'artist': {'id': 'a1', 'name': 'Test Artist', 'sort-name': 'Test Artist'}}],
                'release-group': {'id': 'rg1', 'primary-type': 'Album'},
                'date': '2020',
                'country': 'US',
                'medium-list': [{'format': 'CD'}],
                'medium-count': 1,
                'track-count': 1,
            }]
        }
        self.cluster._lookup_finished(document, Mock(), None)
        self.tagger.move_files_to_album.assert_called_once()

    def test_mb_no_match_discogs_fallback(self):
        """When MB finds nothing but Discogs had a match, use Discogs tags."""
        self.cluster._discogs_candidates = [{
            'id': 99999,
            'title': 'Test Album',
            'artists': [{'name': 'Test Artist'}],
            'year': 2020,
            'genres': ['Rock'],
            'styles': [],
            'labels': [],
            'tracklist': [
                {'type_': 'track', 'title': 'Track 1', 'position': '1', 'duration': '3:20'},
            ],
            'images': [],
        }]

        self.cluster._lookup_finished({'releases': []}, Mock(), None)
        self.assertEqual(self.cluster.files[0].metadata['album'], 'Test Album')
        self.assertEqual(self.cluster.files[0].metadata['albumartist'], 'Test Artist')

    def test_mb_no_match_no_discogs_itunes_called(self):
        """When MB and Discogs find nothing, iTunes is tried."""
        self.cluster._discogs_candidates = []

        self.cluster._lookup_finished({'releases': []}, Mock(), None)
        self.tagger.webservice.download_url.assert_called_once()
        call_kwargs = self.tagger.webservice.download_url.call_args
        url = str(call_kwargs.kwargs.get('url', call_kwargs[1].get('url', '')))
        self.assertIn('itunes.apple.com', url)
