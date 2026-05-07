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

import json
from unittest.mock import (
    Mock,
    patch,
)

from test.picardtestcase import PicardTestCase

from picard.coverart.providers.itunes import (
    ARTWORK_SIZE,
    ITunesCoverArtProvider,
)


class FakeCoverArt:
    def __init__(self, album, metadata, release):
        self.album = album
        self.release = release
        self.metadata = metadata
        self.front_image_found = False


class ITunesProviderTest(PicardTestCase):

    def setUp(self):
        super().setUp()
        self.album = Mock()
        self.album.id = 'test-album-id'
        self.album.tagger = self.tagger
        self.metadata = Mock()
        self.metadata.get.side_effect = lambda key, default='': {
            'album': 'OK Computer',
            'albumartist': 'Radiohead',
        }.get(key, default)
        self.metadata.getraw.return_value = ['Radiohead']
        self.release = {}
        self.coverart = FakeCoverArt(self.album, self.metadata, self.release)
        self.provider = ITunesCoverArtProvider(self.coverart)
        self.provider.metadata = self.metadata

    def test_queue_images_sends_search(self):
        """queue_images should call webservice.download_url with iTunes API URL."""
        result = self.provider.queue_images()
        self.assertEqual(result.name, 'WAIT')
        self.tagger.webservice.download_url.assert_called_once()
        call_kwargs = self.tagger.webservice.download_url.call_args
        url = str(call_kwargs.kwargs.get('url', call_kwargs[1].get('url', '')))
        self.assertIn('itunes.apple.com', url)
        self.assertIn('Radiohead', url)
        self.assertIn('OK+Computer', url.replace('%20', '+').replace('OK Computer', 'OK+Computer'))

    def test_queue_images_no_artist(self):
        """Should return FINISHED if no artist name available."""
        self.metadata.getraw.return_value = []
        self.metadata.get.side_effect = lambda key, default='': {
            'album': 'OK Computer',
            'albumartist': '',
        }.get(key, default)
        result = self.provider.queue_images()
        self.assertEqual(result.name, 'FINISHED')

    def test_queue_images_no_album(self):
        """Should return FINISHED if no album name available."""
        self.metadata.get.side_effect = lambda key, default='': {
            'album': '',
            'albumartist': 'Radiohead',
        }.get(key, default)
        result = self.provider.queue_images()
        self.assertEqual(result.name, 'FINISHED')

    def test_search_finished_success(self):
        """Should queue cover art image when iTunes returns a matching result."""
        response = json.dumps({
            'results': [{
                'artistName': 'Radiohead',
                'collectionName': 'OK Computer',
                'artworkUrl100': 'https://example.com/art100x100bb.jpg',
            }]
        }).encode('utf-8')

        with patch.object(self.provider, 'queue_put') as mock_put, \
             patch.object(self.provider, 'next_in_queue'):
            self.provider._search_finished('Radiohead', 'OK Computer',
                                           response, Mock(), None)
            mock_put.assert_called_once()
            image = mock_put.call_args[0][0]
            self.assertIn(f'{ARTWORK_SIZE}x{ARTWORK_SIZE}bb', str(image.url))

    def test_search_finished_no_match(self):
        """Should not queue if artist/album similarity is too low."""
        response = json.dumps({
            'results': [{
                'artistName': 'Completely Different Artist',
                'collectionName': 'Completely Different Album',
                'artworkUrl100': 'https://example.com/art100x100bb.jpg',
            }]
        }).encode('utf-8')

        with patch.object(self.provider, 'queue_put') as mock_put, \
             patch.object(self.provider, 'next_in_queue'):
            self.provider._search_finished('Radiohead', 'OK Computer',
                                           response, Mock(), None)
            mock_put.assert_not_called()

    def test_search_finished_error(self):
        """Should handle error gracefully."""
        with patch.object(self.provider, 'queue_put') as mock_put, \
             patch.object(self.provider, 'next_in_queue'):
            self.provider._search_finished('Radiohead', 'OK Computer',
                                           None, Mock(), 'Network error')
            mock_put.assert_not_called()

    def test_search_finished_empty_results(self):
        """Should handle empty results gracefully."""
        response = json.dumps({'results': []}).encode('utf-8')

        with patch.object(self.provider, 'queue_put') as mock_put, \
             patch.object(self.provider, 'next_in_queue'):
            self.provider._search_finished('Radiohead', 'OK Computer',
                                           response, Mock(), None)
            mock_put.assert_not_called()

    def test_artwork_url_resolution(self):
        """Should replace 100x100bb with configured size."""
        response = json.dumps({
            'results': [{
                'artistName': 'Radiohead',
                'collectionName': 'OK Computer',
                'artworkUrl100': 'https://is1-ssl.mzstatic.com/image/100x100bb.jpg',
            }]
        }).encode('utf-8')

        with patch.object(self.provider, 'queue_put') as mock_put, \
             patch.object(self.provider, 'next_in_queue'):
            self.provider._search_finished('Radiohead', 'OK Computer',
                                           response, Mock(), None)
            image = mock_put.call_args[0][0]
            url_str = str(image.url)
            self.assertNotIn('100x100bb', url_str)
            self.assertIn(f'{ARTWORK_SIZE}x{ARTWORK_SIZE}bb', url_str)
