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

import unittest

from picard.matching.discogs_matcher import (
    compute_match_score,
    find_best_candidate,
    match_by_duration,
    match_by_title,
    parse_duration,
)


class TestParseDuration(unittest.TestCase):

    def test_standard_format(self):
        self.assertEqual(parse_duration("5:01"), 301000)

    def test_short_duration(self):
        self.assertEqual(parse_duration("0:30"), 30000)

    def test_long_duration(self):
        self.assertEqual(parse_duration("12:45"), 765000)

    def test_hours_format(self):
        self.assertEqual(parse_duration("1:02:30"), 3750000)

    def test_empty_string(self):
        self.assertEqual(parse_duration(""), 0)

    def test_none_like(self):
        self.assertEqual(parse_duration(""), 0)

    def test_whitespace(self):
        self.assertEqual(parse_duration("  "), 0)

    def test_invalid(self):
        self.assertEqual(parse_duration("abc"), 0)

    def test_whitespace_around(self):
        self.assertEqual(parse_duration(" 3:15 "), 195000)


class TestMatchByDuration(unittest.TestCase):

    def _make_tracks(self, durations):
        """Helper to create Discogs-style track dicts from duration strings."""
        return [{'duration': d, 'type_': 'track', 'title': f'Track {i+1}'}
                for i, d in enumerate(durations)]

    def test_perfect_match(self):
        file_durations = [301000, 240000, 180000]  # 5:01, 4:00, 3:00
        tracks = self._make_tracks(["5:01", "4:00", "3:00"])
        score = match_by_duration(file_durations, tracks)
        self.assertEqual(score, 1.0)

    def test_close_match(self):
        # Within 5 second tolerance
        file_durations = [303000, 242000, 178000]  # ~5:03, ~4:02, ~2:58
        tracks = self._make_tracks(["5:01", "4:00", "3:00"])
        score = match_by_duration(file_durations, tracks)
        self.assertGreater(score, 0.8)

    def test_mismatch(self):
        # Very different durations
        file_durations = [60000, 90000, 120000]  # 1:00, 1:30, 2:00
        tracks = self._make_tracks(["5:01", "8:30", "12:00"])
        score = match_by_duration(file_durations, tracks)
        self.assertLess(score, 0.3)

    def test_different_track_count(self):
        # 3 files vs 5 tracks
        file_durations = [301000, 240000, 180000]
        tracks = self._make_tracks(["5:01", "4:00", "3:00", "6:00", "2:30"])
        score = match_by_duration(file_durations, tracks)
        # Score should be penalized for count mismatch
        self.assertLess(score, 1.0)
        self.assertGreater(score, 0.0)

    def test_unordered_match(self):
        # Same durations but in different order
        file_durations = [180000, 301000, 240000]  # 3:00, 5:01, 4:00
        tracks = self._make_tracks(["5:01", "4:00", "3:00"])
        score = match_by_duration(file_durations, tracks)
        # Should still match well because greedy matching is not order-dependent
        self.assertEqual(score, 1.0)

    def test_empty_files(self):
        tracks = self._make_tracks(["5:01", "4:00"])
        score = match_by_duration([], tracks)
        self.assertEqual(score, 0.0)

    def test_empty_tracks(self):
        score = match_by_duration([301000, 240000], [])
        self.assertEqual(score, 0.0)

    def test_no_duration_data(self):
        file_durations = [301000, 240000]
        tracks = self._make_tracks(["", ""])
        score = match_by_duration(file_durations, tracks)
        # With no duration info, score is based on count only
        self.assertLessEqual(score, 0.5)

    def test_filters_non_track_types(self):
        file_durations = [301000, 240000]
        tracks = [
            {'duration': '5:01', 'type_': 'track', 'title': 'Track 1'},
            {'duration': '4:00', 'type_': 'track', 'title': 'Track 2'},
            {'duration': '', 'type_': 'heading', 'title': 'Side A'},
        ]
        score = match_by_duration(file_durations, tracks)
        self.assertEqual(score, 1.0)


class TestMatchByTitle(unittest.TestCase):

    def _make_tracks(self, titles):
        return [{'title': t, 'type_': 'track'} for t in titles]

    def test_exact_match(self):
        file_titles = ["Smells Like Teen Spirit", "Come As You Are"]
        tracks = self._make_tracks(["Smells Like Teen Spirit", "Come As You Are"])
        score = match_by_title(file_titles, tracks)
        self.assertAlmostEqual(score, 1.0, places=2)

    def test_fuzzy_match(self):
        file_titles = ["Smells Like Teen Spirit", "Come as You Are"]
        tracks = self._make_tracks(["Smells Like Teen Spirit", "Come As You Are"])
        score = match_by_title(file_titles, tracks)
        self.assertGreater(score, 0.9)

    def test_poor_match(self):
        file_titles = ["Completely Different Song", "Another Random Title"]
        tracks = self._make_tracks(["Smells Like Teen Spirit", "Come As You Are"])
        score = match_by_title(file_titles, tracks)
        self.assertLess(score, 0.5)

    def test_empty_files(self):
        tracks = self._make_tracks(["Track 1"])
        score = match_by_title([], tracks)
        self.assertEqual(score, 0.0)

    def test_empty_tracks(self):
        score = match_by_title(["Track 1"], [])
        self.assertEqual(score, 0.0)


class TestComputeMatchScore(unittest.TestCase):

    def test_combined_score(self):
        files_info = [
            {'duration_ms': 301000, 'title': 'Smells Like Teen Spirit'},
            {'duration_ms': 240000, 'title': 'Come As You Are'},
        ]
        release = {
            'tracklist': [
                {'duration': '5:01', 'title': 'Smells Like Teen Spirit', 'type_': 'track'},
                {'duration': '4:00', 'title': 'Come As You Are', 'type_': 'track'},
            ]
        }
        score = compute_match_score(files_info, release)
        # Both duration and title should match perfectly
        self.assertAlmostEqual(score, 1.0, places=2)

    def test_no_tracklist(self):
        files_info = [{'duration_ms': 301000, 'title': 'Track 1'}]
        release = {}
        score = compute_match_score(files_info, release)
        self.assertEqual(score, 0.0)


class TestFindBestCandidate(unittest.TestCase):

    def test_picks_best(self):
        files_info = [
            {'duration_ms': 301000, 'title': 'Track 1'},
            {'duration_ms': 240000, 'title': 'Track 2'},
        ]
        candidates = [
            {
                'id': 1,
                'tracklist': [
                    {'duration': '8:00', 'title': 'Wrong Track', 'type_': 'track'},
                    {'duration': '7:00', 'title': 'Wrong Track 2', 'type_': 'track'},
                ]
            },
            {
                'id': 2,
                'tracklist': [
                    {'duration': '5:01', 'title': 'Track 1', 'type_': 'track'},
                    {'duration': '4:00', 'title': 'Track 2', 'type_': 'track'},
                ]
            },
        ]
        best = find_best_candidate(files_info, candidates)
        self.assertIsNotNone(best)
        self.assertEqual(best['id'], 2)

    def test_empty_candidates(self):
        files_info = [{'duration_ms': 301000, 'title': 'Track 1'}]
        best = find_best_candidate(files_info, [])
        self.assertIsNone(best)

    def test_empty_files(self):
        candidates = [{'id': 1, 'tracklist': [{'duration': '5:01', 'title': 'Track 1', 'type_': 'track'}]}]
        best = find_best_candidate([], candidates)
        self.assertIsNone(best)


if __name__ == '__main__':
    unittest.main()
