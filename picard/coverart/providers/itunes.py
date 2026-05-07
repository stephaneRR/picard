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

"""iTunes Search API cover art provider.

Uses the free iTunes Search API (no API key required) to find album
artwork by artist and album name.
"""

from functools import partial
import json
from urllib.parse import urlencode

from PyQt6.QtCore import QUrl

from picard import log
from picard.coverart.image import CoverArtImage
from picard.coverart.providers.provider import CoverArtProvider
from picard.i18n import N_
from picard.util.astrcmp import astrcmp
from picard.webservice import ratecontrol


ITUNES_HOST = "itunes.apple.com"
ITUNES_PORT = 443
ITUNES_BASE_URL = f"https://{ITUNES_HOST}:{ITUNES_PORT}"

# iTunes Search API allows ~20 calls/minute; be conservative
ratecontrol.set_minimum_delay_for_url(ITUNES_BASE_URL, 500)

ARTWORK_SIZE = 600
MIN_SIMILARITY = 0.6


class ITunesCoverArtProvider(CoverArtProvider):

    NAME = 'iTunes'
    TITLE = N_('iTunes')

    def queue_images(self):
        artist = self._get_artist()
        album = self.metadata.get('album', '')
        if not artist or not album:
            log.debug("iTunes: no artist or album name available")
            return CoverArtProvider.QueueState.FINISHED

        term = f"{artist} {album}"
        queryargs = urlencode({
            'term': term,
            'media': 'music',
            'entity': 'album',
            'limit': '5',
        })
        path = f"/search?{queryargs}"

        log.debug("iTunes: searching for %r", term)
        self.album.tagger.webservice.download_url(
            url=QUrl(f"{ITUNES_BASE_URL}{path}"),
            handler=partial(self._search_finished, artist, album),
            priority=True,
        )
        return CoverArtProvider.QueueState.WAIT

    def _search_finished(self, artist, album, data, http, error):
        try:
            if error:
                log.debug("iTunes: search error: %s", error)
                return
            if not data:
                log.debug("iTunes: empty response")
                return

            try:
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                response = json.loads(data)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                log.debug("iTunes: failed to parse response: %s", e)
                return

            results = response.get('results', [])
            if not results:
                log.debug("iTunes: no results found")
                return

            for result in results:
                result_artist = result.get('artistName', '')
                result_album = result.get('collectionName', '')

                if astrcmp(artist.lower(), result_artist.lower()) < MIN_SIMILARITY:
                    log.debug("iTunes: artist mismatch: %r vs %r", artist, result_artist)
                    continue
                if astrcmp(album.lower(), result_album.lower()) < MIN_SIMILARITY:
                    log.debug("iTunes: album mismatch: %r vs %r", album, result_album)
                    continue

                artwork_url = result.get('artworkUrl100', '')
                if not artwork_url:
                    continue

                # Replace 100x100 with high resolution
                artwork_url = artwork_url.replace(
                    '100x100bb', f'{ARTWORK_SIZE}x{ARTWORK_SIZE}bb')

                log.debug("iTunes: found cover for %r - %r: %s",
                          result_artist, result_album, artwork_url)
                self.queue_put(CoverArtImage(artwork_url))
                return

            log.debug("iTunes: no matching result found")
        finally:
            self.next_in_queue()

    def _get_artist(self):
        artists = self.metadata.getraw('~albumartists')
        if artists:
            return artists[0]
        return self.metadata.get('albumartist', '')
