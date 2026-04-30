# -*- coding: utf-8 -*-
#
# Picard, the next-generation MusicBrainz tagger
#
# Originally from the Deezer cover art plugin:
# Copyright (C) Fabio Forni <livingsilver94>
# License: GPL-3.0-or-later
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


import enum
import json
from functools import partial
from typing import (
    Any,
    Mapping,
    Optional,
    Union,
)
from urllib.parse import urlsplit

from PyQt6.QtNetwork import QNetworkReply

from picard import log
from picard.config import (
    FloatOption,
    TextOption,
    get_config,
)
from picard.coverart.image import CoverArtImage
from picard.coverart.providers.provider import (
    CoverArtProvider,
    ProviderOptions,
)
from picard.i18n import N_
from picard.util.astrcmp import astrcmp


# ---------------------------------------------------------------------------
# Deezer API object model (inlined from plugin's deezer/obj.py)
# ---------------------------------------------------------------------------

class APIObject:
    """Base class for Deezer API objects."""
    fields: list[str] = []

    def __init__(self, **kwargs):
        if len(self.fields) == 0:
            raise NotImplementedError(type(self).__name__ + ' cannot have an empty field list')
        for field in self.fields:
            setattr(self, field, kwargs.get(field))

    def __eq__(self, other):
        for field in self.fields:
            if getattr(self, field) != getattr(other, field):
                return False
        return True


class Artist(APIObject):
    """The Artist API object."""
    fields = ['name']


class CoverSize(enum.Enum):
    """Cover size selector."""
    THUMBNAIL = 'small'
    SMALL = ''
    MEDIUM = 'medium'
    BIG = 'big'
    LARGE = 'xl'


class Album(APIObject):
    """The Album API object."""
    fields = ['title', 'cover']

    def cover_url(self, cover_size: CoverSize) -> str:
        """Get the album cover URL based on the size wanted."""
        return '{}?size={}'.format(self.cover, cover_size.value)


class Track(APIObject):
    """The Track API object."""
    fields = ['album', 'artist']


_available_objects = {c.__name__.lower(): c for c in APIObject.__subclasses__()}


def _dict_to_object(data: Mapping[str, Any]) -> Optional[APIObject]:
    try:
        obj_type = data['type']
        obj_class = _available_objects[obj_type]
    except KeyError:
        return None
    else:
        return obj_class(**data)


def parse_json(data: Union[str, Mapping[str, Any]]) -> Optional[APIObject]:
    if isinstance(data, str):
        return json.loads(data, object_hook=_dict_to_object)

    def convert_inner(d: Mapping[str, Any]):
        for k, v in d.items():
            if isinstance(v, dict):
                d[k] = convert_inner(v)
        return _dict_to_object(d)

    convert_inner(data)
    return _dict_to_object(data)


# ---------------------------------------------------------------------------
# Deezer API client (inlined from plugin's deezer/client.py)
# ---------------------------------------------------------------------------

DEEZER_HOST = 'api.deezer.com'
DEEZER_PORT = 443


class SearchOptions:
    """Options for the advanced search."""

    def __init__(self, artist='', album='', track='', label=''):
        self.artist = artist
        self.album = album
        self.track = track
        self.label = label

    def __str__(self):
        parts = []
        for k in ('artist', 'album', 'track', 'label'):
            v = getattr(self, k)
            if v:
                parts.append('{}:"{}"'.format(k, v))
        return ' '.join(parts)


class DeezerClient:
    def __init__(self, webservice):
        self.webservice = webservice

    def advanced_search(self, options: SearchOptions, callback):
        url = 'https://%s:%d/search?q=%s' % (DEEZER_HOST, DEEZER_PORT, str(options))

        def handler(document, reply, error):
            try:
                if isinstance(document, bytes):
                    document = document.decode('utf-8')
                parsed_doc = json.loads(document)
            except (json.JSONDecodeError, UnicodeDecodeError):
                callback([], error)
            else:
                result = []
                err = None
                if 'data' in parsed_doc:
                    result = [parse_json(dct) for dct in parsed_doc['data']]
                elif 'error' in parsed_doc:
                    err = parsed_doc['error'].get('message', 'Deezer responded with an unknown error')
                else:
                    err = 'Deezer returned an unexpected response'
                callback(result, err)

        self.webservice.get_url(
            url=url,
            handler=handler,
            priority=True,
            important=False,
            parse_response_type=None,
        )

    def obj_from_url(self, url: str, callback):
        api_path = self._remove_language_path(urlsplit(url).path)
        api_url = 'https://%s:%d%s' % (DEEZER_HOST, DEEZER_PORT, api_path)

        def handler(document, reply, error):
            try:
                if isinstance(document, bytes):
                    document = document.decode('utf-8')
                deezer_obj = parse_json(document)
            except (json.JSONDecodeError, UnicodeDecodeError):
                deezer_obj = None
            finally:
                callback(deezer_obj, error)

        self.webservice.get_url(
            url=api_url,
            handler=handler,
            priority=True,
            important=False,
            parse_response_type=None,
        )

    @staticmethod
    def _remove_language_path(path: str) -> str:
        # Deezer has a 2-letter language path, e.g. /us/track/123.
        lang_len = 2
        paths = path[1:].split('/', maxsplit=1)
        return path[lang_len + 1:] if len(paths[0]) == lang_len else path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEFAULT_SIMILARITY_THRESHOLD = 0.6


def _is_similar(str1: str, str2: str, min_similarity: float = DEFAULT_SIMILARITY_THRESHOLD) -> bool:
    if str1 in str2:
        return True
    return astrcmp(str1, str2) >= min_similarity


def _is_deezer_url(url: str) -> bool:
    return 'deezer.com' in urlsplit(url).netloc


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

class DeezerCoverArtProvider(CoverArtProvider):

    NAME = 'Deezer'
    TITLE = N_('Deezer')

    _log_prefix = 'Deezer: '

    def __init__(self, coverart):
        super().__init__(coverart)
        self.client = DeezerClient(self.album.tagger.webservice)
        self._has_url_relation = False
        self._retry_search = False

    def queue_images(self):
        self.match_url_relations(['free streaming'], self._url_callback)
        if not self._has_url_relation:
            config = get_config()
            if not self._retry_search:
                search_opts = SearchOptions(artist=self._artist(), album=self.metadata['album'])
            else:
                try:
                    track = self.release['media'][0]['tracks'][1]['title']
                except (IndexError, KeyError):
                    self.error('cannot find a track name to retry a search. No cover found')
                    return CoverArtProvider.QueueState.FINISHED
                else:
                    search_opts = SearchOptions(artist=self._artist(), track=track)
            self.client.advanced_search(search_opts, self._queue_from_search)
        self.album._requests += 1
        return CoverArtProvider.QueueState.WAIT

    def error(self, msg):
        super().error(self._log_prefix + msg)

    def _log_debug(self, msg: str, *args):
        log.debug(self._log_prefix + msg, *args)

    def _url_callback(self, url: str):
        if _is_deezer_url(url):
            self._has_url_relation = True
            self.client.obj_from_url(url, self._queue_from_url)

    def _queue_from_url(self, album: Optional[APIObject], error):
        self.album._requests -= 1
        try:
            if error:
                self.error('could not get Deezer API object: {}'.format(error))
                return
            if not isinstance(album, Album):
                self.error('API object is not an album')
                return
            config = get_config()
            cover_url = album.cover_url(CoverSize(config.setting['deezerart_size']))
            self.queue_put(CoverArtImage(cover_url))
            self._log_debug('queued cover using an URL relation')
        finally:
            self.next_in_queue()

    def _queue_from_search(self, results: list, error):
        self.album._requests -= 1
        try:
            if error:
                self.error('could not fetch search results: {}'.format(error))
                return
            if len(results) == 0:
                if self._retry_search:
                    self.error('no results found')
                    return
                self._retry_search = True
                self.queue_images()
                return
            config = get_config()
            artist = self._artist()
            album_title = self.metadata['album']
            min_similarity = config.setting['deezerart_min_similarity']
            for result in results:
                if not isinstance(result, Track):
                    continue
                if not _is_similar(artist, result.artist.name, min_similarity):
                    self._log_debug('artist similarity below threshold: %r ~ %r', artist, result.artist.name)
                    continue
                if not _is_similar(album_title, result.album.title, min_similarity):
                    self._log_debug('album similarity below threshold: %r ~ %r', album_title, result.album.title)
                    continue
                cover_url = result.album.cover_url(CoverSize(config.setting['deezerart_size']))
                self.queue_put(CoverArtImage(cover_url))
                self._log_debug('queued cover using a Deezer search')
                return
            self.error('no result matched the criteria')
        finally:
            self.next_in_queue()

    def _artist(self) -> str:
        # If there are many artists, we want to search
        # the album in Deezer with just one as keyword.
        # Deezer may not specify all the artists
        # MusicBrainz does, or it may use different separators.
        return self.metadata.getraw('~albumartists')[0]
