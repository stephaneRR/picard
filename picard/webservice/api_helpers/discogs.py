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

"""Discogs API client using Picard's webservice infrastructure."""

import json

from picard import log
from picard.config import get_config
from picard.webservice import (
    PendingRequest,
    ReplyHandler,
    WebService,
    ratecontrol,
)

from .apihelper import APIHelper


DISCOGS_HOST = "api.discogs.com"
DISCOGS_PORT = 443
DISCOGS_BASE_URL = f"https://{DISCOGS_HOST}:{DISCOGS_PORT}"
USER_AGENT = "PicardAlt/1.0 +https://github.com/stephaneRR/picard"

# 60 req/min authenticated = 1 req/s minimum delay
ratecontrol.set_minimum_delay_for_url(DISCOGS_BASE_URL, 1000)


class DiscogsAPIHelper(APIHelper):
    """Helper class for interacting with the Discogs API.

    Uses Picard's webservice infrastructure for HTTP requests,
    rate limiting, and request queuing.
    """

    def __init__(self, webservice: WebService):
        super().__init__(webservice, base_url=DISCOGS_BASE_URL)

    def _get_token(self) -> str:
        """Get the Discogs API token from configuration."""
        config = get_config()
        return config.setting['discogs_token']

    def _make_headers(self) -> dict[str, str]:
        """Build request headers with User-Agent and optional auth token."""
        headers = {
            'User-Agent': USER_AGENT,
        }
        token = self._get_token()
        if token:
            headers['Authorization'] = f'Discogs token={token}'
        return headers

    def _parse_json_response(self, document, reply, error, callback):
        """Parse a raw response into JSON and pass to callback.

        Args:
            document: Raw response body (bytes or str).
            reply: QNetworkReply object.
            error: Error object if request failed.
            callback: Function to call with (parsed_dict, error).
        """
        if error:
            log.error("Discogs API error: %s", error)
            callback(None, error)
            return

        try:
            if isinstance(document, bytes):
                document = document.decode('utf-8')
            parsed = json.loads(document)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            log.error("Discogs API: failed to parse response: %s", e)
            callback(None, e)
            return

        callback(parsed, None)

    def search_releases(self, artist: str, title: str, handler,
                        per_page: int = 5) -> PendingRequest:
        """Search Discogs for releases matching artist and title.

        Args:
            artist: Artist name to search for.
            title: Release title to search for.
            handler: Callback function(document_dict, error).
            per_page: Maximum number of results per page.

        Returns:
            PendingRequest for the search query.
        """
        def response_handler(document, reply, error):
            self._parse_json_response(document, reply, error, handler)

        queryargs = {
            'type': 'release',
            'per_page': str(per_page),
        }
        if artist:
            queryargs['artist'] = artist
        if title:
            queryargs['release_title'] = title

        return self.get(
            "/database/search",
            response_handler,
            unencoded_queryargs=queryargs,
            headers=self._make_headers(),
            priority=True,
            important=False,
            parse_response_type=None,
        )

    def get_release(self, release_id: int, handler) -> PendingRequest:
        """Get full release details including tracklist.

        Args:
            release_id: Discogs release ID.
            handler: Callback function(document_dict, error).

        Returns:
            PendingRequest for the release detail query.
        """
        def response_handler(document, reply, error):
            self._parse_json_response(document, reply, error, handler)

        return self.get(
            f"/releases/{release_id}",
            response_handler,
            headers=self._make_headers(),
            priority=True,
            important=False,
            parse_response_type=None,
        )
