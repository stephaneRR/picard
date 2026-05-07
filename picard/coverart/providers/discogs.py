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

"""Discogs cover art provider.

Uses cached Discogs release data from the matching phase when available,
or falls back to searching the Discogs API by artist and album name.
Requires a Discogs token to be configured.
"""

from functools import partial

from picard import log
from picard.config import get_config
from picard.coverart.image import CoverArtImage
from picard.coverart.providers.provider import CoverArtProvider
from picard.i18n import N_


def _best_image_url(images):
    """Extract the best cover art URL from Discogs images list.

    Prefers 'primary' type images, then largest by width.
    Returns the resource_url of the best image, or None.
    """
    if not images:
        return None

    primary = [img for img in images if img.get('type') == 'primary']
    candidates = primary if primary else images

    best = max(candidates, key=lambda img: img.get('width', 0), default=None)
    if best:
        return best.get('resource_url') or best.get('uri')
    return None


class DiscogsCoverArtProvider(CoverArtProvider):

    NAME = 'Discogs'
    TITLE = N_('Discogs')

    def enabled(self):
        config = get_config()
        if not config.setting.get('discogs_enabled', True):
            return False
        return super().enabled()

    def queue_images(self):
        # Try cached data from Discogs matching phase
        cached = self._get_cached_discogs_data()
        if cached:
            images = cached.get('images', [])
            url = _best_image_url(images)
            if url:
                prefetched = self._get_prefetched_data(url)
                if prefetched:
                    log.debug("Discogs: using pre-fetched cover (%d bytes): %s",
                              len(prefetched), url)
                    self.queue_put(CoverArtImage(url=url, data=prefetched))
                else:
                    log.debug("Discogs: using cached URL from matching phase: %s", url)
                    self.queue_put(CoverArtImage(url))
                return CoverArtProvider.QueueState.FINISHED
            log.debug("Discogs: cached data has no images")

        # Fall back to API search
        config = get_config()
        token = config.setting.get('discogs_token', '')
        if not token:
            log.debug("Discogs: no API token configured, skipping search")
            return CoverArtProvider.QueueState.FINISHED

        artist = self._get_artist()
        album = self.metadata.get('album', '')
        if not artist or not album:
            log.debug("Discogs: no artist or album name available")
            return CoverArtProvider.QueueState.FINISHED

        log.debug("Discogs: searching for %r - %r", artist, album)
        self.album.tagger.discogs_api.search_releases(
            artist, album,
            handler=partial(self._search_finished),
            per_page=3,
        )
        return CoverArtProvider.QueueState.WAIT

    def _search_finished(self, results, error):
        try:
            if error:
                log.debug("Discogs: search error: %s", error)
                return
            if not results:
                log.debug("Discogs: no results")
                return

            search_results = results.get('results', []) if isinstance(results, dict) else []
            if not search_results:
                log.debug("Discogs: empty results")
                return

            # Use the first result's cover_image or thumb
            for result in search_results:
                cover_url = result.get('cover_image', '') or result.get('thumb', '')
                if cover_url and 'spacer.gif' not in cover_url:
                    log.debug("Discogs: found cover from search: %s", cover_url)
                    self.queue_put(CoverArtImage(cover_url))
                    return

            log.debug("Discogs: no usable cover image in results")
        finally:
            self.next_in_queue()

    def _get_prefetched_data(self, url):
        """Check if cover image data was pre-downloaded during the matching phase."""
        prefetched = getattr(self.album.tagger, '_prefetched_cover_data', None)
        if prefetched and url in prefetched:
            return prefetched.pop(url)
        return None

    def _get_cached_discogs_data(self):
        """Check if Discogs release data was cached during the matching phase."""
        mbid_cache = getattr(self.album.tagger, '_mbid_to_discogs', None)
        if mbid_cache and self.album.id in mbid_cache:
            return mbid_cache[self.album.id]
        return None

    def _get_artist(self):
        artists = self.metadata.getraw('~albumartists')
        if artists:
            return artists[0]
        return self.metadata.get('albumartist', '')
