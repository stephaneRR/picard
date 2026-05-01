# -*- coding: utf-8 -*-
#
# Picard, the next-generation MusicBrainz tagger
#
# Originally from the fanart.tv cover art plugin:
# Copyright (C) 2015-2021 Philipp Wolfer
# Copyright (C) Sambhav Kothari
# License: GPL-2.0-or-later
#
# Adapted for built-in integration.
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
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.


from functools import partial

from PyQt6.QtCore import QUrl
from PyQt6.QtNetwork import QNetworkReply

from picard import log
from picard.config import (
    get_config,
)
from picard.coverart.image import CoverArtImage
from picard.coverart.providers.provider import (
    CoverArtProvider,
)
from picard.i18n import N_


FANART_HOST = "webservice.fanart.tv"
FANART_PORT = 443
FANART_APIKEY = "21305dd1589766f4d544535ad4df12f4"

OPTION_CDART_ALWAYS = "always"
OPTION_CDART_NEVER = "never"
OPTION_CDART_NOALBUMART = "noalbumart"


def _cover_sort_key(cover):
    """For sorting a list of cover arts by likes."""
    try:
        return int(cover["likes"]) if "likes" in cover else 0
    except ValueError:
        return 0


def _encode_queryarg(arg):
    return bytes(QUrl.toPercentEncoding(arg)).decode()


class FanartTvCoverArtImage(CoverArtImage):
    """Image from fanart.tv"""
    support_types = True
    sourceprefix = "FATV"


class FanartTvCoverArtProvider(CoverArtProvider):

    """Use fanart.tv to get cover art"""

    NAME = "fanart.tv"
    TITLE = N_("fanart.tv")

    def enabled(self):
        return (self._client_key and super().enabled()
                and not self.coverart.front_image_found)

    def queue_images(self):
        release_group_id = self.metadata["musicbrainz_releasegroupid"]
        path = "/v3/music/albums/%s" % (release_group_id, )
        url = "https://%s:%d%s" % (FANART_HOST, FANART_PORT, path)
        queryargs = {
            "api_key": _encode_queryarg(FANART_APIKEY),
            "client_key": _encode_queryarg(self._client_key),
        }
        log.debug("FanartTvCoverArtProvider.queue_images: %s", path)
        self.album.tagger.webservice.get_url(
            url=url,
            handler=partial(self._json_downloaded, release_group_id),
            priority=True,
            important=False,
            parse_response_type='json',
            queryargs=queryargs,
        )
        self.album._requests += 1
        return CoverArtProvider.QueueState.WAIT

    @property
    def _client_key(self):
        config = get_config()
        return config.setting["fanarttv_client_key"]

    def _json_downloaded(self, release_group_id, data, reply, error):
        self.album._requests -= 1

        if error:
            if error != QNetworkReply.NetworkError.ContentNotFoundError:
                error_level = log.error
            else:
                error_level = log.debug
            error_level("Problem requesting metadata in fanart.tv provider: %s",
                        error)
        else:
            try:
                config = get_config()
                release = data["albums"][release_group_id]
                has_cover = "albumcover" in release
                has_cdart = "cdart" in release
                use_cdart = config.setting["fanarttv_use_cdart"]

                if has_cover:
                    covers = release["albumcover"]
                    self._select_and_add_cover_art(covers, ["front"])

                if has_cdart and (use_cdart == OPTION_CDART_ALWAYS
                                  or (use_cdart == OPTION_CDART_NOALBUMART
                                      and not has_cover)):
                    covers = release["cdart"]
                    types = ["medium"]
                    if not has_cover:
                        types.append("front")
                    self._select_and_add_cover_art(covers, types)
            except (AttributeError, KeyError, TypeError):
                log.error("Problem processing downloaded metadata in fanart.tv provider", exc_info=True)

        self.next_in_queue()

    def _select_and_add_cover_art(self, covers, types):
        covers = sorted(covers, key=_cover_sort_key, reverse=True)
        url = covers[0]["url"]
        log.debug("FanartTvCoverArtProvider found artwork %s", url)
        self.queue_put(FanartTvCoverArtImage(url, types=types))
