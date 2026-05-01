# -*- coding: utf-8 -*-
#
# Picard, the next-generation MusicBrainz tagger
#
# Copyright (C) 2004 Robert Kaye
# Copyright (C) 2006-2008, 2011 Lukáš Lalinský
# Copyright (C) 2008 Hendrik van Antwerpen
# Copyright (C) 2008 Will
# Copyright (C) 2010-2011, 2014, 2018-2026 Philipp Wolfer
# Copyright (C) 2011-2013 Michael Wiencek
# Copyright (C) 2012 Chad Wilson
# Copyright (C) 2012 Wieland Hoffmann
# Copyright (C) 2013-2015, 2018-2021, 2023-2024 Laurent Monin
# Copyright (C) 2014, 2017 Sophist-UK
# Copyright (C) 2016 Rahul Raturi
# Copyright (C) 2016-2017 Sambhav Kothari
# Copyright (C) 2017 Antonio Larrosa
# Copyright (C) 2018 Vishal Choudhary
# Copyright (C) 2020 Gabriel Ferreira
# Copyright (C) 2020 Ray Bouchard
# Copyright (C) 2021 Petit Minion
# Copyright (C) 2024 Giorgio Fontanive
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


from collections import (
    Counter,
    defaultdict,
)
from collections.abc import Iterable
from operator import attrgetter
import re
from typing import TYPE_CHECKING
import weakref

from functools import partial

from picard import log
from picard.config import get_config
from picard.file import File
from picard.i18n import (
    N_,
    gettext as _,
)
from picard.item import (
    FileListItem,
    Item,
)
from picard.matching.discogs_matcher import (
    compute_match_score,
    find_best_candidate,
)
from picard.metadata import SimMatchRelease
from picard.track import Track
from picard.util import (
    album_artist_from_path,
    find_best_match,
    format_time,
)

from picard.ui.enums import MainAction


if TYPE_CHECKING:
    from picard.album import Album

# Weights for different elements when comparing a cluster to a release
CLUSTER_COMPARISON_WEIGHTS = {
    'album': 17,
    'albumartist': 6,
    'date': 4,
    'format': 2,
    'releasecountry': 2,
    'releasetype': 10,
    'totalalbumtracks': 10,
}


class FileList(FileListItem):
    def __init__(self, files=None):
        super().__init__(files=files)
        if self.files and self.can_show_coverart:
            for file in self.files:
                file.metadata_images_changed.connect(self.update_metadata_images)
            self.update_metadata_images_from_children()

    def update(self, signal=True):
        pass

    @property
    def can_show_coverart(self) -> bool:
        return True


class Cluster(FileList):
    def __init__(self, name: str, artist="", special=False, related_album: 'Album | None' = None, hide_if_empty=False):
        super().__init__()
        self.metadata['album'] = name
        self.metadata['albumartist'] = artist
        self.metadata['totaltracks'] = 0
        self.special = special
        self.hide_if_empty = hide_if_empty
        self.album = related_album
        self._lookup_task = None

    @property
    def album(self) -> 'Album | None':
        if self._album is None:
            return None
        return self._album()

    @album.setter
    def album(self, value: 'Album | None'):
        self._album = weakref.ref(value) if value is not None else None

    def __repr__(self):
        if self.album:
            return '<Cluster %s %r>' % (
                self.album.id,
                self.album.metadata['album'] + '/' + self.metadata['album'],
            )
        return '<Cluster %r>' % self.metadata['album']

    def __len__(self):
        return len(self.files)

    def __bool__(self):
        # Ensure even a cluster without files (len() == 0) is considered truthy
        return True

    def _update_related_album(self, added_files=None, removed_files=None):
        if self.album:
            if added_files:
                self.album.add_metadata_images_from_children(added_files)
            if removed_files:
                self.album.remove_metadata_images_from_children(removed_files)
            self.album.update()

    def add_files(self, files: Iterable[File], new_album=True):
        added_files = set(files) - set(self.files)
        if not added_files:
            return
        for file in added_files:
            file._move(self)
            file.update(signal=False)
            if self.can_show_coverart:
                file.metadata_images_changed.connect(self.update_metadata_images)
        added_files = sorted(added_files, key=attrgetter('discnumber', 'tracknumber', 'base_filename'))
        self.files.extend(added_files)
        self.update(signal=False)
        if self.can_show_coverart:
            self.add_metadata_images_from_children(added_files)
        if self.ui_item:
            self.ui_item.add_files(added_files)
        if new_album:
            self._update_related_album(added_files=added_files)

    def add_file(self, file: File, new_album=True):
        self.add_files([file], new_album=new_album)

    def remove_file(self, file: File, new_album=True):
        self.tagger.window.set_processing(True)
        try:
            self.files.remove(file)
        except ValueError as e:
            log.debug("File %r already removed from cluster %r: %s", file, self, e)
            self.tagger.window.set_processing(False)
            return
        self.update(signal=False)
        if self.ui_item:
            self.ui_item.remove_file(file)
        if self.can_show_coverart:
            file.metadata_images_changed.disconnect(self.update_metadata_images)
            self.remove_metadata_images_from_children([file])
        if new_album:
            self._update_related_album(removed_files=[file])
        self.tagger.window.set_processing(False)
        if not self.special and self.get_num_files() == 0:
            self.tagger.remove_cluster(self)

    def update(self, signal=True):
        self.metadata['~totalalbumtracks'] = self.metadata['totaltracks'] = len(self.files)
        if signal and self.ui_item:
            self.ui_item.update()

    def get_num_files(self):
        return len(self.files)

    @property
    def can_save(self):
        """Return if this object can be saved."""
        return bool(self.files)

    @property
    def can_remove(self):
        """Return if this object can be removed."""
        return not self.special

    @property
    def can_edit_tags(self) -> bool:
        """Return if this object supports tag editing."""
        return True

    @property
    def can_analyze(self) -> bool:
        """Return if this object can be fingerprinted."""
        return any(_file.can_analyze for _file in self.files)

    @property
    def can_autotag(self) -> bool:
        return True

    @property
    def can_refresh(self) -> bool:
        return False

    @property
    def can_browser_lookup(self) -> bool:
        return not self.special

    @property
    def can_view_info(self) -> bool:
        return bool(self.files)

    @property
    def can_submit(self) -> bool:
        return not self.special and bool(self.files)

    @property
    def is_album_like(self) -> bool:
        return True

    @property
    def is_permanently_hidden(self) -> bool:
        return self.hide_if_empty and not self.files

    def column(self, column: str) -> str:
        if column == 'title':
            return '%s (%d)' % (self.metadata['album'], len(self.files))
        elif self.special and column in {'~length', 'album', 'covercount'}:
            return ''
        elif column == '~length':
            return format_time(self.files.length)
        elif column == 'artist':
            return self.metadata['albumartist']
        elif column == 'tracknumber':
            return self.metadata['totaltracks']
        elif column == 'discnumber':
            return self.metadata['totaldiscs']
        else:
            return super().column(column)

    def _lookup_finished(self, document, http, error):
        self._lookup_task = None

        try:
            releases = document['releases']
        except (KeyError, TypeError):
            releases = None

        def statusbar(message):
            self.tagger.window.set_statusbar_message(
                message,
                {'album': self.metadata['album']},
                timeout=3000,
            )

        best_match_release = None
        if releases:
            config = get_config()
            best_match_release = self._match_to_release(releases, threshold=config.setting['cluster_lookup_threshold'])

        if best_match_release:
            statusbar(N_("Cluster %(album)s identified!"))
            self.tagger.move_files_to_album(self.files, best_match_release['id'])
        else:
            statusbar(N_("No matching releases for cluster %(album)s"))

    def _match_to_release(self, releases, threshold=0):
        # multiple matches -- calculate similarities to each of them
        def candidates():
            for release in releases:
                match_ = self.metadata.compare_to_release(release, CLUSTER_COMPARISON_WEIGHTS)
                if match_.similarity >= threshold:
                    yield match_

        no_match = SimMatchRelease(similarity=-1, release=None)
        best_match = find_best_match(candidates(), no_match)
        return best_match.result.release

    def lookup_metadata(self):
        """Try to identify the cluster using the existing metadata.

        If Discogs enriched search is enabled and a token is configured,
        try Discogs first to get a better match via duration comparison.
        Falls back to standard MusicBrainz search.
        """
        if self._lookup_task or getattr(self, '_discogs_lookup_active', False):
            return
        config = get_config()
        discogs_enabled = config.setting['discogs_enabled']
        discogs_token = config.setting['discogs_token']

        if discogs_enabled and discogs_token:
            self._lookup_via_discogs()
        else:
            self._lookup_via_mb()

    def _lookup_via_mb(self):
        """Standard MusicBrainz lookup (original behavior)."""
        self.tagger.window.set_statusbar_message(
            N_("Looking up the metadata for cluster %(album)s…"),
            {'album': self.metadata['album']},
        )
        config = get_config()
        self._lookup_task = self.tagger.mb_api.find_releases(
            self._lookup_finished,
            artist=self.metadata['albumartist'],
            release=self.metadata['album'],
            tracks=str(len(self.files)),
            limit=config.setting['query_limit'],
        )

    def _get_files_info(self):
        """Gather file info (durations, titles) for matching."""
        files_info = []
        for file in self.files:
            info = {
                'duration_ms': file.metadata.length or 0,
                'title': file.metadata.get('title', '') or file.metadata.get('~filename', ''),
            }
            files_info.append(info)
        return files_info

    def _lookup_via_discogs(self):
        """Try Discogs first to enrich the lookup, then fall back to MB."""
        self._discogs_lookup_active = True
        self.tagger.window.set_statusbar_message(
            N_("Searching Discogs for cluster %(album)s…"),
            {'album': self.metadata['album']},
        )
        artist = self.metadata['albumartist']
        title = self.metadata['album']

        self._lookup_task = self.tagger.discogs_api.search_releases(
            artist, title,
            handler=partial(self._discogs_search_finished),
        )

    def _discogs_search_finished(self, document, error):
        """Handle Discogs search results."""
        if error or not document:
            log.debug("Discogs search failed or empty, falling back to MB: %s", error)
            self._lookup_task = None
            self._lookup_via_mb()
            return

        results = document.get('results', [])
        if not results:
            log.debug("No Discogs results for cluster %r, falling back to MB",
                      self.metadata['album'])
            self._lookup_task = None
            self._lookup_via_mb()
            return

        # Filter candidates by track count if possible
        num_files = len(self.files)
        filtered = []
        for result in results:
            # Discogs search results don't include track count,
            # so we keep the top results and filter later by tracklist
            filtered.append(result)
            if len(filtered) >= 3:
                break

        if not filtered:
            self._lookup_task = None
            self._lookup_via_mb()
            return

        # Fetch release details for each candidate
        self._discogs_candidates = []
        self._discogs_pending = len(filtered)

        for result in filtered:
            release_id = result.get('id')
            if release_id:
                self.tagger.discogs_api.get_release(
                    release_id,
                    handler=partial(self._discogs_release_fetched),
                )
            else:
                self._discogs_pending -= 1

        if self._discogs_pending == 0:
            self._lookup_task = None
            self._lookup_via_mb()

    def _discogs_release_fetched(self, document, error):
        """Handle individual Discogs release detail response."""
        self._discogs_pending -= 1

        if not error and document:
            self._discogs_candidates.append(document)

        # Wait until all candidates have been fetched
        if self._discogs_pending > 0:
            return

        self._lookup_task = None
        files_info = self._get_files_info()

        if not self._discogs_candidates:
            log.debug("No Discogs release details available, falling back to MB")
            self._lookup_via_mb()
            return

        config = get_config()
        threshold = config.setting['discogs_match_threshold']

        best = find_best_candidate(files_info, self._discogs_candidates)
        if best:
            score = compute_match_score(files_info, best)
            if score >= threshold:
                discogs_id = best.get('id')
                discogs_url = f"https://www.discogs.com/release/{discogs_id}"
                log.debug("Discogs match found (score=%.2f): %s", score, discogs_url)

                self.tagger.window.set_statusbar_message(
                    N_("Found Discogs match for cluster %(album)s, looking up on MusicBrainz…"),
                    {'album': self.metadata['album']},
                )

                # Look up the Discogs URL on MusicBrainz to find linked release
                self._lookup_task = self.tagger.mb_api.lookup_urls(
                    [discogs_url],
                    handler=partial(self._discogs_url_lookup_finished),
                    inc=['release-rels'],
                )
                return

        log.debug("No Discogs candidate above threshold (%.2f), falling back to MB", threshold)
        self._discogs_lookup_active = False
        self._lookup_via_mb()

    def _discogs_url_lookup_finished(self, document, http, error):
        """Handle MusicBrainz URL lookup response for Discogs URL."""
        self._lookup_task = None
        self._discogs_lookup_active = False

        if error or not document:
            log.debug("MB URL lookup failed, falling back to MB search: %s", error)
            self._lookup_via_mb()
            return

        # Try to extract a release MBID from the URL entity relations
        # MB /ws/2/url response nests data under a 'url' key
        try:
            url_entity = document.get('url', document)
            relations = url_entity.get('relations', [])
            for rel in relations:
                if rel.get('type') == 'discogs' and 'release' in rel:
                    release_id = rel['release'].get('id')
                    if release_id:
                        log.info("Discogs enriched search found MB release: %s", release_id)
                        self.tagger.window.set_statusbar_message(
                            N_("Cluster %(album)s identified via Discogs!"),
                            {'album': self.metadata['album']},
                            timeout=3000,
                        )
                        self.tagger.move_files_to_album(self.files, release_id)
                        return
        except (KeyError, TypeError, AttributeError) as e:
            log.debug("Error parsing MB URL lookup response: %s", e)

        log.debug("No MB release linked to Discogs URL, falling back to MB search")
        self._lookup_via_mb()

    def clear_lookup_task(self):
        if self._lookup_task:
            self.tagger.webservice.abort_task(self._lookup_task)
            self._lookup_task = None

    @staticmethod
    def cluster(files: Iterable[File]):
        """Group the provided files into clusters, based on album tag in metadata.

        Args:
            files: List of File objects.

        Yields:
            FileCluster objects
        """
        config = get_config()
        various_artists = config.setting['va_name']

        cluster_list: dict[str, FileCluster] = defaultdict(FileCluster)
        for file in files:
            # If the file is attached to a track we should use the original
            # metadata for clustering. This is often used by users when moving
            # mismatched files back from the right pane to the left.
            if isinstance(file.parent_item, Track):
                metadata = file.orig_metadata
            else:
                metadata = file.metadata
            artist = metadata['albumartist'] or metadata['artist']
            album = metadata['album']

            # Improve clustering from directory structure if no existing tags
            # Only used for grouping and to provide cluster title / artist - not added to file tags.
            album, artist = album_artist_from_path(file.filename, album, artist)

            token = tokenize(album)
            if token:
                cluster_list[token].add(album, artist or various_artists, file)

        yield from cluster_list.values()


class UnclusteredFiles(Cluster):
    """Special cluster for 'Unmatched Files' which have not been clustered."""

    def __init__(self):
        super().__init__(_("Unclustered Files"), special=True)

    def add_files(self, files, new_album=True):
        super().add_files(files, new_album=new_album)
        self.tagger.window.enable_action(MainAction.CLUSTER, self.files)

    def remove_file(self, file, new_album=True):
        super().remove_file(file, new_album=new_album)
        self.tagger.window.enable_action(MainAction.CLUSTER, self.files)

    def lookup_metadata(self):
        self.tagger.autotag(self.files)

    @property
    def can_edit_tags(self):
        return False

    @property
    def can_autotag(self):
        return bool(self.files)

    @property
    def can_view_info(self):
        return False

    @property
    def can_remove(self):
        return bool(self.files)

    @property
    def can_show_coverart(self):
        return False


class ClusterList(list, Item):
    """A list of clusters."""

    def __init__(self, name=None):
        if not name:
            self._name = _('Clusters')
        else:
            self._name = name
        super().__init__()

    def __hash__(self):
        return id(self)

    def __bool__(self):
        # An existing Item object should not be considered False, even if it
        # is based on a list.
        return True

    def column(self, column: str) -> str:
        if column == 'title':
            return '%s (%d)' % (self._name, len(self))
        else:
            return ''

    def iterfiles(self, save=False):
        for cluster in self:
            yield from cluster.iterfiles(save)

    @property
    def can_save(self):
        return len(self) > 0

    @property
    def can_analyze(self):
        return any(cluster.can_analyze for cluster in self)

    @property
    def can_autotag(self):
        return len(self) > 0

    @property
    def can_browser_lookup(self):
        return False

    def lookup_metadata(self):
        for cluster in self:
            cluster.lookup_metadata()


class FileCluster:
    def __init__(self):
        self._files = []
        self._artist_counts = Counter()
        self._artists = defaultdict(Counter)
        self._titles = Counter()

    def add(self, album, artist, file):
        self._files.append(file)
        token = tokenize(artist)
        self._artist_counts[token] += 1
        self._artists[token][artist] += 1
        self._titles[album] += 1

    @property
    def files(self):
        yield from (file for file in self._files if file.state != File.State.REMOVED)

    @property
    def artist(self):
        tokenized_artist = self._artist_counts.most_common(1)[0][0]
        candidates = self._artists[tokenized_artist]
        return candidates.most_common(1)[0][0]

    @property
    def title(self):
        # Find the most common title
        return self._titles.most_common(1)[0][0]


_re_non_alphanum = re.compile(r'\W', re.UNICODE)
_re_spaces = re.compile(r'\s', re.UNICODE)


def tokenize(word):
    word = word.lower()
    token = _re_non_alphanum.sub('', word)
    return token if token else _re_spaces.sub('', word)
