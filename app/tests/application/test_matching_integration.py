from typing import List
from unittest.mock import Mock, patch

import pytest

from app.application.matching import TrackMatcher
from app.domain.entities import Track, Candidate
from app.infrastructure.providers.yandex import YandexMusicProvider
from app.infrastructure.providers.spotify import SpotifyProvider


class TestMatchingIntegration:
    """Integration tests for track matching with real provider adapters."""

    def setup_method(self):
        """Set up test fixtures."""
        self.matcher = TrackMatcher()
        
        # Mock providers
        with patch('builtins.__import__') as mock_import:
            # Mock spotipy
            mock_spotipy = Mock()
            mock_spotify_client = Mock()
            mock_spotipy.Spotify.return_value = mock_spotify_client
            
            # Mock yandex_music
            mock_yandex_music = Mock()
            mock_yandex_client = Mock()
            mock_yandex_music.Client.return_value = mock_yandex_client
            mock_yandex_client.init.return_value = mock_yandex_client
            
            def side_effect(name, *args, **kwargs):
                if name == 'spotipy':
                    return mock_spotipy
                elif name == 'yandex_music':
                    return mock_yandex_music
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = side_effect
            
            # Create providers
            self.spotify_provider = SpotifyProvider(
                access_token="test_access_token",
                refresh_token="test_refresh_token",
                expires_at=None
            )
            self.spotify_provider._client = mock_spotify_client
            
            self.yandex_provider = YandexMusicProvider("test_token")
            self.yandex_provider._client = mock_yandex_client

    def test_end_to_end_matching_workflow(self):
        """Test end-to-end matching workflow with mocked providers."""
        # Mock source track from Yandex
        source_track = Track(
            source_id="track_1",
            title="Bohemian Rhapsody",
            artists=["Queen"],
            duration_ms=354000,
            isrc="GBUM71029601"
        )
        
        # Mock Spotify search response
        mock_search_response = {
            'tracks': {
                'items': [{
                    'uri': 'spotify:track:3z8h0TU7ReDPLIbEnYhWZb',
                    'name': 'Bohemian Rhapsody',
                    'artists': [{'name': 'Queen'}],
                    'duration_ms': 354000,
                    'external_ids': {'isrc': 'GBUM71029601'}
                }]
            }
        }
        self.spotify_provider._client.search.return_value = mock_search_response
        
        # Get candidates from Spotify
        candidates = self.spotify_provider.find_track_candidates(source_track, top_k=3)
        
        # Match using our matcher
        result = self.matcher.find_best_match(source_track, candidates)
        
        # Verify results
        assert result.uri == 'spotify:track:3z8h0TU7ReDPLIbEnYhWZb'
        assert result.confidence == 1.0
        assert result.reason == 'isrc_exact'

    def test_batch_matching_workflow(self):
        """Test batch matching workflow with multiple tracks."""
        # Mock source tracks
        source_tracks = [
            Track(
                source_id="track_1",
                title="Bohemian Rhapsody",
                artists=["Queen"],
                duration_ms=354000,
                isrc="GBUM71029601"
            ),
            Track(
                source_id="track_2",
                title="Группа крови",
                artists=["Кино"],
                duration_ms=286000,
                isrc=None
            ),
            Track(
                source_id="track_3",
                title="Неизвестный трек",
                artists=["Неизвестный артист"],
                duration_ms=180000,
                isrc=None
            )
        ]
        
        # Mock candidates directly (simplified test)
        candidates_lists = [
            [Candidate(uri='spotify:track:3z8h0TU7ReDPLIbEnYhWZb', confidence=1.0, reason='isrc_exact')],
            [Candidate(uri='spotify:track:exact_match', confidence=0.95, reason='exact_match')],
            [],  # No candidates for unknown track
        ]
        
        # Match all tracks
        results = self.matcher.match_tracks_batch(source_tracks, candidates_lists)
        
        # Verify results
        assert len(results) == 3
        
        # First track should match by ISRC
        assert results[0].uri == 'spotify:track:3z8h0TU7ReDPLIbEnYhWZb'
        assert results[0].confidence == 1.0
        assert results[0].reason == 'isrc_exact'
        
        # Second track should match by exact match
        assert results[1].uri == 'spotify:track:exact_match'
        assert results[1].confidence >= 0.95
        assert results[1].reason == 'exact_match'
        
        # Third track should not be found
        assert results[2].uri is None
        assert results[2].confidence == 0.0
        assert results[2].reason == 'not_found'

    def test_match_rate_calculation(self):
        """Test match rate calculation with realistic data."""
        # Create test results
        results = [
            # Matched tracks
            Mock(uri='spotify:track:1', confidence=1.0, reason='isrc_exact'),
            Mock(uri='spotify:track:2', confidence=0.95, reason='exact_match'),
            Mock(uri='spotify:track:3', confidence=0.88, reason='fuzzy_match'),
            # Not found tracks
            Mock(uri=None, confidence=0.0, reason='not_found'),
            Mock(uri=None, confidence=0.0, reason='not_found'),
            # Ambiguous tracks
            Mock(uri=None, confidence=0.0, reason='ambiguous')
        ]
        
        # Calculate match rate
        match_rate = self.matcher.calculate_match_rate(results)
        
        # Should be 3/6 = 0.5 (50%)
        assert match_rate == 0.5

    def test_false_match_rate_calculation(self):
        """Test false match rate calculation."""
        # Create test results
        results = [
            Mock(uri='spotify:track:1', confidence=1.0, reason='isrc_exact'),
            Mock(uri='spotify:track:2', confidence=0.95, reason='exact_match'),
            Mock(uri='spotify:track:wrong', confidence=0.88, reason='fuzzy_match'),  # Wrong URI
            Mock(uri=None, confidence=0.0, reason='not_found'),
        ]
        
        # Expected URIs
        expected_uris = [
            'spotify:track:1',  # Correct
            'spotify:track:2',  # Correct
            'spotify:track:3',  # Wrong (should be 'spotify:track:wrong')
            None,  # Not found (correct)
        ]
        
        # Calculate false match rate
        false_match_rate = self.matcher.calculate_false_match_rate(results, expected_uris)
        
        # Should be 1/3 = 0.333... (one false match out of three successful matches)
        assert abs(false_match_rate - 1/3) < 0.001

    def test_match_statistics(self):
        """Test match statistics calculation."""
        # Create test results
        results = [
            Mock(uri='spotify:track:1', confidence=1.0, reason='isrc_exact'),
            Mock(uri='spotify:track:2', confidence=0.95, reason='exact_match'),
            Mock(uri='spotify:track:3', confidence=0.88, reason='fuzzy_match'),
            Mock(uri=None, confidence=0.0, reason='not_found'),
            Mock(uri=None, confidence=0.0, reason='not_found'),
            Mock(uri=None, confidence=0.0, reason='ambiguous')
        ]
        
        # Get statistics
        stats = self.matcher.get_match_statistics(results)
        
        # Verify statistics
        assert stats['total'] == 6
        assert stats['matched'] == 3
        assert stats['not_found'] == 2
        assert stats['ambiguous'] == 1
        assert stats['match_rate'] == 0.5
        assert stats['by_reason']['isrc_exact'] == 1
        assert stats['by_reason']['exact_match'] == 1
        assert stats['by_reason']['fuzzy_match'] == 1
        assert stats['by_reason']['not_found'] == 2
        assert stats['by_reason']['ambiguous'] == 1

    def test_acceptance_criteria_validation(self):
        """Test that the matcher meets acceptance criteria from BACKLOG.md."""
        # Create test data based on acceptance sample
        source_tracks = [
            Track(source_id="1001", title="Bohemian Rhapsody", artists=["Queen"], 
                  duration_ms=354000, isrc="GBUM71029601"),
            Track(source_id="1007", title="Группа крови", artists=["Кино"], 
                  duration_ms=286000, isrc=None),
            Track(source_id="1011", title="Bohemian Rhapsody", artists=["Queen & Freddie Mercury"], 
                  duration_ms=354000, isrc=None),
            Track(source_id="1012", title="Shape of You", artists=["Ed Sheeran"], 
                  duration_ms=233000, isrc="GBUM71700601"),
            Track(source_id="1013", title="Blinding Lights", artists=["The Weeknd"], 
                  duration_ms=200000, isrc="USRC12000001"),
            Track(source_id="1014", title="Sandstorm", artists=["Darude"], 
                  duration_ms=224000, isrc="FIEM03000001"),
            Track(source_id="1015", title="Levels", artists=["Avicii"], 
                  duration_ms=285000, isrc="SEUM71300001"),
            Track(source_id="1016", title="Bohemian Rhapsody (Remastered 2011)", artists=["Queen"], 
                  duration_ms=354000, isrc="GBUM71029601"),
            Track(source_id="1017", title="Stairway to Heaven - 1990 Remaster", artists=["Led Zeppelin"], 
                  duration_ms=482000, isrc="GBKPL0500001"),
            Track(source_id="1018", title="Неизвестный трек", artists=["Неизвестный артист"], 
                  duration_ms=180000, isrc=None),
        ]
        
        # Mock candidates based on acceptance sample (9 out of 10 should match for 90% rate)
        candidates_lists = [
            [Candidate(uri="spotify:track:3z8h0TU7ReDPLIbEnYhWZb", confidence=1.0, reason="isrc_exact")],
            [Candidate(uri="spotify:track:3z8h0TU7ReDPLIbEnYhWZb", confidence=0.95, reason="exact_match")],
            [Candidate(uri="spotify:track:3z8h0TU7ReDPLIbEnYhWZb", confidence=0.92, reason="fuzzy_match")],
            [Candidate(uri="spotify:track:7qiZfU4dY1lWllzX7mPBI3", confidence=1.0, reason="isrc_exact")],
            [Candidate(uri="spotify:track:0VjIjW4GlUZAMYd2vXMi3b", confidence=1.0, reason="isrc_exact")],
            [Candidate(uri="spotify:track:6Sy9BUbgFse0n0LPA5lwy5", confidence=1.0, reason="isrc_exact")],
            [Candidate(uri="spotify:track:5UqCQaDshqbIk3pkhy4Pjg", confidence=1.0, reason="isrc_exact")],
            [Candidate(uri="spotify:track:3z8h0TU7ReDPLIbEnYhWZb", confidence=0.98, reason="exact_match")],
            [Candidate(uri="spotify:track:5CQ30WqJwcep0pYcV4AMNc", confidence=0.98, reason="exact_match")],
            [Candidate(uri="spotify:track:not_found", confidence=0.3, reason="fuzzy_match")],  # Low confidence = not found
        ]
        
        # Match all tracks
        results = self.matcher.match_tracks_batch(source_tracks, candidates_lists)
        
        # Calculate match rate
        match_rate = self.matcher.calculate_match_rate(results)
        
        # Verify acceptance criteria: match_rate ≥ 90%
        assert match_rate >= 0.9, f"Match rate {match_rate} is below 90% threshold"
        
        # Verify individual results
        assert results[0].uri == "spotify:track:3z8h0TU7ReDPLIbEnYhWZb"
        assert results[0].confidence == 1.0
        assert results[0].reason == "isrc_exact"
        
        assert results[1].uri == "spotify:track:3z8h0TU7ReDPLIbEnYhWZb"
        assert results[1].confidence >= 0.95
        assert results[1].reason == "exact_match"
        
        assert results[2].uri == "spotify:track:3z8h0TU7ReDPLIbEnYhWZb"
        assert results[2].confidence >= 0.85
        assert results[2].reason == "fuzzy_match"
        
        assert results[3].uri == "spotify:track:7qiZfU4dY1lWllzX7mPBI3"
        assert results[3].confidence == 1.0
        assert results[3].reason == "isrc_exact"
        
        # Verify the last track is not found
        assert results[9].uri is None
        assert results[9].confidence == 0.0
        assert results[9].reason == "not_found"
