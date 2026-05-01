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
    patch,
)

from test.picardtestcase import PicardTestCase

from picard.webservice.api_helpers.discogs import (
    DISCOGS_BASE_URL,
    USER_AGENT,
    DiscogsAPIHelper,
)


class TestDiscogsAPIHelper(PicardTestCase):

    def setUp(self):
        super().setUp()
        self.set_config_values(setting={
            'discogs_token': 'test_token_123',
        })
        self.mock_webservice = MagicMock()
        self.mock_webservice.get_url = MagicMock(return_value=MagicMock())
        self.api = DiscogsAPIHelper(self.mock_webservice)

    def test_base_url(self):
        """Verify the base URL is set correctly."""
        self.assertEqual(str(self.api.base_url.toString()), DISCOGS_BASE_URL)

    def test_get_token(self):
        """Verify token is read from config."""
        token = self.api._get_token()
        self.assertEqual(token, 'test_token_123')

    def test_get_token_empty(self):
        """Verify empty token when not configured."""
        self.set_config_values(setting={'discogs_token': ''})
        token = self.api._get_token()
        self.assertEqual(token, '')

    def test_make_headers_with_token(self):
        """Verify headers include authorization when token is set."""
        headers = self.api._make_headers()
        self.assertEqual(headers['User-Agent'], USER_AGENT)
        self.assertEqual(headers['Authorization'], 'Discogs token=test_token_123')

    def test_make_headers_without_token(self):
        """Verify headers exclude authorization when no token."""
        self.set_config_values(setting={'discogs_token': ''})
        headers = self.api._make_headers()
        self.assertEqual(headers['User-Agent'], USER_AGENT)
        self.assertNotIn('Authorization', headers)

    def test_search_releases_calls_get(self):
        """Verify search_releases constructs the right API call."""
        handler = MagicMock()
        self.api.search_releases('Nirvana', 'Nevermind', handler)

        # The APIHelper.get() should have been called, which calls webservice.get_url
        self.mock_webservice.get_url.assert_called_once()

        call_kwargs = self.mock_webservice.get_url.call_args[1]
        url = call_kwargs['url']
        url_str = url.toString()

        self.assertIn('api.discogs.com', url_str)
        self.assertIn('/database/search', url_str)

    def test_get_release_calls_get(self):
        """Verify get_release constructs the right API call."""
        handler = MagicMock()
        self.api.get_release(249504, handler)

        self.mock_webservice.get_url.assert_called_once()

        call_kwargs = self.mock_webservice.get_url.call_args[1]
        url = call_kwargs['url']
        url_str = url.toString()

        self.assertIn('api.discogs.com', url_str)
        self.assertIn('/releases/249504', url_str)

    def test_parse_json_response_success(self):
        """Verify JSON parsing on success."""
        callback = MagicMock()
        self.api._parse_json_response(
            b'{"results": []}', MagicMock(), None, callback
        )
        callback.assert_called_once()
        result, error = callback.call_args[0]
        self.assertEqual(result, {"results": []})
        self.assertIsNone(error)

    def test_parse_json_response_error(self):
        """Verify error handling on request error."""
        callback = MagicMock()
        self.api._parse_json_response(
            None, MagicMock(), Exception("network error"), callback
        )
        callback.assert_called_once()
        result, error = callback.call_args[0]
        self.assertIsNone(result)
        self.assertIsNotNone(error)

    def test_parse_json_response_invalid_json(self):
        """Verify error handling on invalid JSON."""
        callback = MagicMock()
        self.api._parse_json_response(
            b'not valid json', MagicMock(), None, callback
        )
        callback.assert_called_once()
        result, error = callback.call_args[0]
        self.assertIsNone(result)
        self.assertIsNotNone(error)

    def test_search_headers_include_token(self):
        """Verify the token is included in the request headers."""
        handler = MagicMock()
        self.api.search_releases('Nirvana', 'Nevermind', handler)

        call_kwargs = self.mock_webservice.get_url.call_args[1]
        headers = call_kwargs.get('headers', {})
        self.assertIn('Authorization', headers)
        self.assertEqual(headers['Authorization'], 'Discogs token=test_token_123')
        self.assertEqual(headers['User-Agent'], USER_AGENT)
