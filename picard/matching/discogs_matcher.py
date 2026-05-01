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

"""Matching logic for comparing file metadata against Discogs releases."""

from difflib import SequenceMatcher
import re


def parse_duration(duration_str: str) -> int:
    """Parse a Discogs duration string like '5:01' to milliseconds.

    Args:
        duration_str: Duration in 'M:SS' or 'H:MM:SS' format.

    Returns:
        Duration in milliseconds. Returns 0 for empty or invalid strings.
    """
    if not duration_str or not duration_str.strip():
        return 0

    duration_str = duration_str.strip()
    parts = duration_str.split(':')

    try:
        if len(parts) == 2:
            minutes, seconds = int(parts[0]), int(parts[1])
            return (minutes * 60 + seconds) * 1000
        elif len(parts) == 3:
            hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
            return (hours * 3600 + minutes * 60 + seconds) * 1000
    except (ValueError, IndexError):
        pass

    return 0


def _normalize_title(title: str) -> str:
    """Normalize a track title for comparison.

    Lowercases, removes punctuation, and collapses whitespace.
    """
    title = title.lower().strip()
    title = re.sub(r'[^\w\s]', '', title)
    title = re.sub(r'\s+', ' ', title)
    return title


def match_by_duration(file_durations_ms: list[int], discogs_tracks: list[dict],
                      tolerance_ms: int = 5000) -> float:
    """Score how well file durations match Discogs tracklist durations.

    Uses a greedy matching approach (not order-dependent). Each file duration
    is matched to the closest unmatched Discogs track duration within tolerance.

    Args:
        file_durations_ms: List of file durations in milliseconds.
        discogs_tracks: List of Discogs track dicts with 'duration' key.
        tolerance_ms: Maximum allowed difference in milliseconds.

    Returns:
        A score between 0.0 and 1.0.
    """
    # Filter out non-track entries (e.g. headings, index tracks)
    actual_tracks = [t for t in discogs_tracks if t.get('type_', 'track') == 'track']

    discogs_durations = []
    for track in actual_tracks:
        dur = parse_duration(track.get('duration', ''))
        discogs_durations.append(dur)

    if not file_durations_ms or not discogs_durations:
        return 0.0

    # Penalize track count mismatch
    count_ratio = min(len(file_durations_ms), len(discogs_durations)) / max(len(file_durations_ms), len(discogs_durations))

    # Skip duration matching if Discogs has no duration data
    valid_discogs_durations = [d for d in discogs_durations if d > 0]
    if not valid_discogs_durations:
        # No duration data available from Discogs, score based on track count only
        return count_ratio * 0.5

    # Greedy matching: for each file duration, find best matching Discogs duration
    remaining = list(range(len(discogs_durations)))
    matched = 0
    total_files = len(file_durations_ms)

    for file_dur in file_durations_ms:
        best_idx = None
        best_diff = float('inf')

        for idx in remaining:
            discogs_dur = discogs_durations[idx]
            if discogs_dur == 0:
                continue
            diff = abs(file_dur - discogs_dur)
            if diff < best_diff:
                best_diff = diff
                best_idx = idx

        if best_idx is not None and best_diff <= tolerance_ms:
            remaining.remove(best_idx)
            matched += 1

    if total_files == 0:
        return 0.0

    duration_score = matched / total_files
    return duration_score * count_ratio


def match_by_title(file_titles: list[str], discogs_tracks: list[dict]) -> float:
    """Score how well file titles match Discogs track titles using fuzzy matching.

    Args:
        file_titles: List of file track titles.
        discogs_tracks: List of Discogs track dicts with 'title' key.

    Returns:
        A score between 0.0 and 1.0.
    """
    actual_tracks = [t for t in discogs_tracks if t.get('type_', 'track') == 'track']

    if not file_titles or not actual_tracks:
        return 0.0

    discogs_titles = [_normalize_title(t.get('title', '')) for t in actual_tracks]

    total_score = 0.0
    matched_count = 0

    for file_title in file_titles:
        normalized_file = _normalize_title(file_title)
        if not normalized_file:
            continue

        best_ratio = 0.0
        for discogs_title in discogs_titles:
            if not discogs_title:
                continue
            ratio = SequenceMatcher(None, normalized_file, discogs_title).ratio()
            if ratio > best_ratio:
                best_ratio = ratio

        total_score += best_ratio
        matched_count += 1

    if matched_count == 0:
        return 0.0

    return total_score / matched_count


def compute_match_score(files_info: list[dict], discogs_release: dict) -> float:
    """Combined score from duration + title matching.

    Duration matching is weighted more heavily (0.7) than title matching (0.3)
    because duration is a more reliable indicator of the correct edition.

    Args:
        files_info: List of dicts with 'duration_ms' and 'title' keys.
        discogs_release: Discogs release dict with 'tracklist' key.

    Returns:
        A score between 0.0 and 1.0.
    """
    tracklist = discogs_release.get('tracklist', [])
    if not tracklist:
        return 0.0

    file_durations = [f.get('duration_ms', 0) for f in files_info]
    file_titles = [f.get('title', '') for f in files_info]

    duration_score = match_by_duration(file_durations, tracklist)
    title_score = match_by_title(file_titles, tracklist)

    # Weight duration higher as it identifies the exact edition
    return 0.7 * duration_score + 0.3 * title_score


def find_best_candidate(files_info: list[dict],
                        discogs_releases: list[dict]) -> dict | None:
    """Find the best matching Discogs release for the given files.

    Args:
        files_info: List of dicts with 'duration_ms' and 'title' keys.
        discogs_releases: List of Discogs release detail dicts.

    Returns:
        The best matching release dict, or None if no candidate scores
        above 0.0.
    """
    if not files_info or not discogs_releases:
        return None

    best_release = None
    best_score = 0.0

    for release in discogs_releases:
        score = compute_match_score(files_info, release)
        if score > best_score:
            best_score = score
            best_release = release

    return best_release
