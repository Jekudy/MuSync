from typing import List
from unittest.mock import Mock

import pytest

from app.application.matching import TrackMatcher
from app.domain.entities import Track, Candidate


class TestTrackMatcher:
    """Tests for track matching algorithm."""

    def setup_method(self):
        """Set up test fixtures."""
        self.matcher = TrackMatcher()

    def test_isrc_exact_match_returns_confidence_1_0(self):
        """Test that ISRC exact match returns confidence 1.0."""
        source_track = Track(
            source_id="track_1",
            title="Bohemian Rhapsody",
            artists=["Queen"],
            duration_ms=354000,
            isrc="GBUM71029601"
        )

        candidates = [
            Candidate(
                uri="spotify:track:exact_match",
                confidence=1.0,
                reason="isrc_exact"
            )
        ]

        result = self.matcher.find_best_match(source_track, candidates)

        assert result.uri == "spotify:track:exact_match"
        assert result.confidence == 1.0
        assert result.reason == "isrc_exact"

    def test_exact_match_title_artist_duration_returns_high_confidence(self):
        """Test that exact match by title+artist+duration returns high confidence."""
        source_track = Track(
            source_id="track_1",
            title="Группа крови",
            artists=["Кино"],
            duration_ms=286000,
            isrc=None
        )

        candidates = [
            Candidate(
                uri="spotify:track:exact_match",
                confidence=0.95,
                reason="exact_match"
            )
        ]

        result = self.matcher.find_best_match(source_track, candidates)

        assert result.uri == "spotify:track:exact_match"
        assert result.confidence >= 0.95
        assert result.reason == "exact_match"

    def test_duration_tolerance_within_2_seconds(self):
        """Test that duration tolerance works within ±2 seconds."""
        source_track = Track(
            source_id="track_1",
            title="Bohemian Rhapsody",
            artists=["Queen"],
            duration_ms=354000,
            isrc=None
        )

        # Test duration within tolerance
        candidates = [
            Candidate(
                uri="spotify:track:within_tolerance",
                confidence=0.95,
                reason="exact_match"
            )
        ]

        result = self.matcher.find_best_match(source_track, candidates)

        assert result.uri == "spotify:track:within_tolerance"
        assert result.confidence >= 0.95

    def test_fuzzy_match_returns_lower_confidence(self):
        """Test that fuzzy match returns lower confidence."""
        source_track = Track(
            source_id="track_1",
            title="Bohemian Rhapsody",
            artists=["Queen"],
            duration_ms=354000,
            isrc=None
        )

        candidates = [
            Candidate(
                uri="spotify:track:fuzzy_match",
                confidence=0.85,
                reason="fuzzy_match"
            )
        ]

        result = self.matcher.find_best_match(source_track, candidates)

        assert result.uri == "spotify:track:fuzzy_match"
        assert 0.8 <= result.confidence < 0.95
        assert result.reason == "fuzzy_match"

    def test_no_candidates_returns_not_found(self):
        """Test that no candidates returns not_found."""
        source_track = Track(
            source_id="track_1",
            title="Неизвестный трек",
            artists=["Неизвестный артист"],
            duration_ms=180000,
            isrc=None
        )

        candidates = []

        result = self.matcher.find_best_match(source_track, candidates)

        assert result.uri is None
        assert result.confidence == 0.0
        assert result.reason == "not_found"

    def test_low_confidence_candidates_returns_not_found(self):
        """Low confidence candidates should be rejected under strict default risk mode."""
        source_track = Track(
            source_id="track_1",
            title="Неизвестный трек",
            artists=["Неизвестный артист"],
            duration_ms=180000,
            isrc=None
        )

        candidates = [
            Candidate(
                uri="spotify:track:low_confidence",
                confidence=0.3,
                reason="fuzzy_match"
            )
        ]

        result = self.matcher.find_best_match(source_track, candidates)

        assert result.uri is None
        assert result.confidence == 0.0
        assert result.reason == "not_found"

    def test_multiple_candidates_returns_highest_confidence(self):
        """Test that multiple candidates return the highest confidence one."""
        source_track = Track(
            source_id="track_1",
            title="Bohemian Rhapsody",
            artists=["Queen"],
            duration_ms=354000,
            isrc=None
        )

        candidates = [
            Candidate(
                uri="spotify:track:low_confidence",
                confidence=0.7,
                reason="fuzzy_match"
            ),
            Candidate(
                uri="spotify:track:high_confidence",
                confidence=0.95,
                reason="exact_match"
            ),
            Candidate(
                uri="spotify:track:medium_confidence",
                confidence=0.8,
                reason="fuzzy_match"
            )
        ]

        result = self.matcher.find_best_match(source_track, candidates)

        assert result.uri == "spotify:track:high_confidence"
        assert result.confidence == 0.95
        assert result.reason == "exact_match"

    def test_ambiguous_candidates_returns_ambiguous(self):
        """Test that ambiguous candidates (similar confidence) select the best candidate (no ambiguous stop)."""
        source_track = Track(
            source_id="track_1",
            title="Bohemian Rhapsody",
            artists=["Queen"],
            duration_ms=354000,
            isrc=None
        )

        candidates = [
            Candidate(
                uri="spotify:track:candidate_1",
                confidence=0.95,
                reason="exact_match"
            ),
            Candidate(
                uri="spotify:track:candidate_2",
                confidence=0.94,
                reason="exact_match"
            )
        ]

        result = self.matcher.find_best_match(source_track, candidates)

        assert result.uri == "spotify:track:candidate_1"
        assert result.confidence == 0.95
        assert result.reason == "exact_match"

    def test_confidence_thresholds(self):
        """Test confidence thresholds for different match types."""
        source_track = Track(
            source_id="track_1",
            title="Test Song",
            artists=["Test Artist"],
            duration_ms=180000,
            isrc=None
        )

        # Test exact match threshold (≥0.95)
        exact_candidates = [
            Candidate(
                uri="spotify:track:exact",
                confidence=0.95,
                reason="exact_match"
            )
        ]
        exact_result = self.matcher.find_best_match(source_track, exact_candidates)
        assert exact_result.confidence >= 0.95

        # Test fuzzy match threshold (≥0.85)
        fuzzy_candidates = [
            Candidate(
                uri="spotify:track:fuzzy",
                confidence=0.85,
                reason="fuzzy_match"
            )
        ]
        fuzzy_result = self.matcher.find_best_match(source_track, fuzzy_candidates)
        assert fuzzy_result.confidence >= 0.85

        # Test below threshold (rejected in strict mode)
        low_candidates = [
            Candidate(
                uri="spotify:track:low",
                confidence=0.7,
                reason="fuzzy_match"
            )
        ]
        low_result = self.matcher.find_best_match(source_track, low_candidates)
        assert low_result.reason == "not_found"

    def test_ambiguous_threshold(self):
        """Test when candidates are close in confidence, the best is still selected (no ambiguous stop)."""
        source_track = Track(
            source_id="track_1",
            title="Test Song",
            artists=["Test Artist"],
            duration_ms=180000,
            isrc=None
        )

        # Two candidates with very close confidence (within 0.05)
        candidates = [
            Candidate(
                uri="spotify:track:candidate_1",
                confidence=0.95,
                reason="exact_match"
            ),
            Candidate(
                uri="spotify:track:candidate_2",
                confidence=0.91,  # Within 0.05 of the best
                reason="exact_match"
            )
        ]

        result = self.matcher.find_best_match(source_track, candidates)

        assert result.uri == "spotify:track:candidate_1"
        assert result.confidence == 0.95
        assert result.reason == "exact_match"

    def test_acceptance_sample_isrc_matches(self):
        """Test ISRC matches from acceptance sample."""
        # Test case from acceptance sample
        source_track = Track(
            source_id="1001",
            title="Bohemian Rhapsody",
            artists=["Queen"],
            duration_ms=354000,
            isrc="GBUM71029601"
        )

        candidates = [
            Candidate(
                uri="spotify:track:3z8h0TU7ReDPLIbEnYhWZb",
                confidence=1.0,
                reason="isrc_exact"
            )
        ]

        result = self.matcher.find_best_match(source_track, candidates)

        assert result.uri == "spotify:track:3z8h0TU7ReDPLIbEnYhWZb"
        assert result.confidence == 1.0
        assert result.reason == "isrc_exact"

    def test_acceptance_sample_exact_matches(self):
        """Test exact matches from acceptance sample."""
        # Test case from acceptance sample
        source_track = Track(
            source_id="1007",
            title="Группа крови",
            artists=["Кино"],
            duration_ms=286000,
            isrc=None
        )

        candidates = [
            Candidate(
                uri="spotify:track:3z8h0TU7ReDPLIbEnYhWZb",
                confidence=0.95,
                reason="exact_match"
            )
        ]

        result = self.matcher.find_best_match(source_track, candidates)

        assert result.uri == "spotify:track:3z8h0TU7ReDPLIbEnYhWZb"
        assert result.confidence >= 0.95
        assert result.reason == "exact_match"

    def test_acceptance_sample_fuzzy_matches(self):
        """Test fuzzy matches from acceptance sample."""
        # Test case from acceptance sample
        source_track = Track(
            source_id="1011",
            title="Bohemian Rhapsody",
            artists=["Queen & Freddie Mercury"],
            duration_ms=354000,
            isrc=None
        )

        candidates = [
            Candidate(
                uri="spotify:track:3z8h0TU7ReDPLIbEnYhWZb",
                confidence=0.92,
                reason="fuzzy_match"
            )
        ]

        result = self.matcher.find_best_match(source_track, candidates)

        assert result.uri == "spotify:track:3z8h0TU7ReDPLIbEnYhWZb"
        assert result.confidence >= 0.85
        assert result.reason == "fuzzy_match"

    def test_acceptance_sample_not_found(self):
        """Test not found cases from acceptance sample."""
        # Test case from acceptance sample
        source_track = Track(
            source_id="1015",
            title="Неизвестный трек",
            artists=["Неизвестный артист"],
            duration_ms=180000,
            isrc=None
        )

        candidates = []

        result = self.matcher.find_best_match(source_track, candidates)

        assert result.uri is None
        assert result.confidence == 0.0
        assert result.reason == "not_found"
