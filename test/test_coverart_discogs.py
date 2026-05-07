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

from picard.coverart.providers.discogs import (
    DiscogsCoverArtProvider,
    _best_image_url,
)


class BestImageUrlTest(PicardTestCase):

    def test_primary_image_preferred(self):
        images = [
            {'type': 'secondary', 'width': 800, 'resource_url': 'http://img/secondary.jpg'},
            {'type': 'primary', 'width': 600, 'resource_url': 'http://img/primary.jpg'},
        ]
        self.assertEqual(_best_image_url(images), 'http://img/primary.jpg')

    def test_largest_secondary_when_no_primary(self):
        images = [
            {'type': 'secondary', 'width': 300, 'resource_url': 'http://img/small.jpg'},
            {'type': 'secondary', 'width': 800, 'resource_url': 'http://img/large.jpg'},
        ]
        self.assertEqual(_best_image_url(images), 'http://img/large.jpg')

    def test_empty_images(self):
        self.assertIsNone(_best_image_url([]))
        self.assertIsNone(_best_image_url(None))

    def test_uri_fallback(self):
        images = [{'type': 'primary', 'width': 500, 'uri': 'http://img/via_uri.jpg'}]
        self.assertEqual(_best_image_url(images), 'http://img/via_uri.jpg')


class FakeCoverArt:
    def __init__(self, album, metadata, release):
        self.album = album
        self.release = release
        self.metadata = metadata
        self.front_image_found = False


class DiscogsCachedDataTest(PicardTestCase):
    """Tests for Discogs provider using cached data from matching phase."""

    def setUp(self):
        super().setUp()
        self.album = Mock()
        self.album.id = 'mbid-test-123'
        self.album.tagger = self.tagger
        self.tagger.discogs_api = Mock()
        self.metadata = Mock()
        self.metadata.get.side_effect = lambda key, default='': {
            'album': 'OK Computer',
            'albumartist': 'Radiohead',
        }.get(key, default)
        self.metadata.getraw.return_value = ['Radiohead']
        self.release = {}
        self.coverart = FakeCoverArt(self.album, self.metadata, self.release)
        self.set_config_values(setting={
            'discogs_enabled': True,
            'discogs_token': 'test_token',
        })

    def test_cached_data_used_directly(self):
        """Provider should use cached Discogs images from matching phase."""
        self.tagger._mbid_to_discogs = {
            'mbid-test-123': {
                'discogs_id': 12345,
                'images': [
                    {'type': 'primary', 'width': 600, 'resource_url': 'http://img/cached.jpg'},
                ],
            }
        }
        provider = DiscogsCoverArtProvider(self.coverart)
        provider.metadata = self.metadata

        with patch.object(provider, 'queue_put') as mock_put:
            result = provider.queue_images()
            self.assertEqual(result.name, 'FINISHED')
            mock_put.assert_called_once()
            image = mock_put.call_args[0][0]
            self.assertIn('cached.jpg', str(image.url))

    def test_no_cached_data_falls_back_to_search(self):
        """Provider should search Discogs API when no cached data."""
        provider = DiscogsCoverArtProvider(self.coverart)
        provider.metadata = self.metadata

        result = provider.queue_images()
        self.assertEqual(result.name, 'WAIT')
        self.tagger.discogs_api.search_releases.assert_called_once()

    def test_cached_data_no_images_falls_back(self):
        """If cached data has no images, fall back to API search."""
        self.tagger._mbid_to_discogs = {
            'mbid-test-123': {
                'discogs_id': 12345,
                'images': [],
            }
        }
        provider = DiscogsCoverArtProvider(self.coverart)
        provider.metadata = self.metadata

        result = provider.queue_images()
        self.assertEqual(result.name, 'WAIT')

    def test_disabled_setting(self):
        """Provider should be disabled when discogs_enabled is False."""
        self.set_config_values(setting={'discogs_enabled': False})
        provider = DiscogsCoverArtProvider(self.coverart)
        self.assertFalse(provider.enabled())

    def test_no_token_skips_search(self):
        """Should return FINISHED without searching if no API token."""
        self.set_config_values(setting={
            'discogs_enabled': True,
            'discogs_token': '',
        })
        provider = DiscogsCoverArtProvider(self.coverart)
        provider.metadata = self.metadata

        result = provider.queue_images()
        self.assertEqual(result.name, 'FINISHED')


class DiscogsSearchResultTest(PicardTestCase):
    """Tests for Discogs provider search result handling."""

    def setUp(self):
        super().setUp()
        self.album = Mock()
        self.album.id = 'mbid-test-456'
        self.album.tagger = self.tagger
        self.tagger.discogs_api = Mock()
        self.metadata = Mock()
        self.metadata.get.side_effect = lambda key, default='': {
            'album': 'OK Computer',
            'albumartist': 'Radiohead',
        }.get(key, default)
        self.metadata.getraw.return_value = ['Radiohead']
        self.release = {}
        self.coverart = FakeCoverArt(self.album, self.metadata, self.release)
        self.set_config_values(setting={
            'discogs_enabled': True,
            'discogs_token': 'test_token',
        })

    def test_search_finished_success(self):
        """Should queue cover art from search results."""
        provider = DiscogsCoverArtProvider(self.coverart)
        provider.metadata = self.metadata

        results = {
            'results': [{
                'cover_image': 'http://img/search_cover.jpg',
                'thumb': 'http://img/search_thumb.jpg',
            }]
        }

        with patch.object(provider, 'queue_put') as mock_put, \
             patch.object(provider, 'next_in_queue'):
            provider._search_finished(results, None)
            mock_put.assert_called_once()
            image = mock_put.call_args[0][0]
            self.assertIn('search_cover.jpg', str(image.url))

    def test_search_finished_spacer_gif_skipped(self):
        """Should skip spacer.gif placeholder images."""
        provider = DiscogsCoverArtProvider(self.coverart)
        provider.metadata = self.metadata

        results = {
            'results': [{
                'cover_image': 'https://st.discogs.com/spacer.gif',
                'thumb': '',
            }]
        }

        with patch.object(provider, 'queue_put') as mock_put, \
             patch.object(provider, 'next_in_queue'):
            provider._search_finished(results, None)
            mock_put.assert_not_called()

    def test_search_finished_error(self):
        """Should handle error gracefully."""
        provider = DiscogsCoverArtProvider(self.coverart)
        provider.metadata = self.metadata

        with patch.object(provider, 'queue_put') as mock_put, \
             patch.object(provider, 'next_in_queue'):
            provider._search_finished(None, 'Network error')
            mock_put.assert_not_called()
