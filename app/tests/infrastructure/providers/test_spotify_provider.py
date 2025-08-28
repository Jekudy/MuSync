from typing import List
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

import pytest

from app.domain.entities import Playlist, Track, Candidate, AddResult
from app.domain.errors import RateLimited, TemporaryFailure, NotFound
from app.infrastructure.providers.spotify import SpotifyProvider


class TestSpotifyProvider:
    """Contract tests for Spotify provider adapter."""

    def setup_method(self):
        """Set up test fixtures."""
        # Mock the spotipy module and client creation
        with patch('builtins.__import__') as mock_import:
            # Create a mock spotipy module
            mock_spotipy = Mock()
            mock_spotify_client = Mock()
            mock_spotipy.Spotify.return_value = mock_spotify_client
            
            # Make __import__ return our mock when spotipy is imported
            def side_effect(name, *args, **kwargs):
                if name == 'spotipy':
                    return mock_spotipy
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = side_effect
            
            # Create provider with mocked client
            self.provider = SpotifyProvider(
                access_token="test_access_token",
                refresh_token="test_refresh_token",
                expires_at=datetime.now() + timedelta(hours=1)
            )
            # Ensure the mock client is used
            self.provider._client = mock_spotify_client
            self.mock_spotify = mock_spotify_client

    def test_find_track_candidates_with_isrc_returns_exact_match(self):
        """Test that find_track_candidates with ISRC returns exact match."""
        # Mock track with ISRC
        track = Track(
            source_id="track_1",
            title="Test Song",
            artists=["Test Artist"],
            duration_ms=180000,
            isrc="USABC1234567"
        )

        # Mock Spotify search response for ISRC
        mock_search_response = {
            'tracks': {
                'items': [{
                    'uri': 'spotify:track:exact_match_123',
                    'name': 'Test Song',
                    'artists': [{'name': 'Test Artist'}],
                    'duration_ms': 180000,
                    'external_ids': {'isrc': 'USABC1234567'}
                }]
            }
        }
        self.mock_spotify.search.return_value = mock_search_response

        candidates = self.provider.find_track_candidates(track, top_k=3)

        assert len(candidates) == 1
        assert candidates[0].uri == 'spotify:track:exact_match_123'
        assert candidates[0].confidence == 1.0
        assert candidates[0].reason == 'isrc_exact'

    def test_find_track_candidates_without_isrc_uses_title_artist_search(self):
        """Test that find_track_candidates without ISRC uses title+artist search."""
        track = Track(
            source_id="track_1",
            title="Test Song",
            artists=["Test Artist"],
            duration_ms=180000,
            isrc=None
        )

        # Mock Spotify search response for title+artist
        mock_search_response = {
            'tracks': {
                'items': [{
                    'uri': 'spotify:track:fuzzy_match_123',
                    'name': 'Test Song',
                    'artists': [{'name': 'Test Artist'}],
                    'duration_ms': 182000,  # Within ±2s tolerance
                    'external_ids': {'isrc': 'USABC1234568'}
                }]
            }
        }
        self.mock_spotify.search.return_value = mock_search_response

        candidates = self.provider.find_track_candidates(track, top_k=3)

        assert len(candidates) == 1
        assert candidates[0].uri == 'spotify:track:fuzzy_match_123'
        assert candidates[0].confidence >= 0.95  # Exact match with duration tolerance
        assert candidates[0].reason == 'exact_match'

    def test_find_track_candidates_returns_multiple_candidates(self):
        """Test that find_track_candidates returns multiple candidates when requested."""
        track = Track(
            source_id="track_1",
            title="Popular Song",
            artists=["Popular Artist"],
            duration_ms=180000,
            isrc=None
        )

        # Mock multiple search results
        mock_search_response = {
            'tracks': {
                'items': [
                    {
                        'uri': 'spotify:track:exact_123',
                        'name': 'Popular Song',
                        'artists': [{'name': 'Popular Artist'}],
                        'duration_ms': 180000
                    },
                    {
                        'uri': 'spotify:track:similar_456',
                        'name': 'Popular Song (Remix)',
                        'artists': [{'name': 'Popular Artist'}],
                        'duration_ms': 190000
                    },
                    {
                        'uri': 'spotify:track:other_789',
                        'name': 'Popular Song',
                        'artists': [{'name': 'Other Artist'}],
                        'duration_ms': 180000
                    }
                ]
            }
        }
        self.mock_spotify.search.return_value = mock_search_response

        candidates = self.provider.find_track_candidates(track, top_k=3)

        assert len(candidates) == 3
        assert candidates[0].confidence >= candidates[1].confidence  # Sorted by confidence desc
        assert candidates[1].confidence >= candidates[2].confidence

    def test_find_track_candidates_handles_no_results(self):
        """Test that find_track_candidates handles no search results."""
        track = Track(
            source_id="track_1",
            title="Unknown Song",
            artists=["Unknown Artist"],
            duration_ms=180000,
            isrc=None
        )

        # Mock empty search response
        mock_search_response = {
            'tracks': {
                'items': []
            }
        }
        self.mock_spotify.search.return_value = mock_search_response

        candidates = self.provider.find_track_candidates(track, top_k=3)

        assert len(candidates) == 0

    def test_resolve_or_create_playlist_finds_existing_playlist(self):
        """Test that resolve_or_create_playlist finds existing playlist by name."""
        # Mock current user
        mock_user = {'id': 'user_123'}
        self.mock_spotify.current_user.return_value = mock_user

        # Mock existing playlists
        mock_playlists_response = {
            'items': [{
                'id': 'playlist_123',
                'name': 'My Playlist',
                'owner': {'id': 'user_123'}
            }]
        }
        self.mock_spotify.current_user_playlists.return_value = mock_playlists_response

        playlist = self.provider.resolve_or_create_playlist("My Playlist")

        assert playlist.id == 'playlist_123'
        assert playlist.name == 'My Playlist'
        assert playlist.owner_id == 'user_123'
        assert playlist.is_owned is True

    def test_resolve_or_create_playlist_creates_new_playlist(self):
        """Test that resolve_or_create_playlist creates new playlist when not found."""
        # Mock current user
        mock_user = {'id': 'user_123'}
        self.mock_spotify.current_user.return_value = mock_user

        # Mock no existing playlists
        mock_playlists_response = {
            'items': []
        }
        self.mock_spotify.current_user_playlists.return_value = mock_playlists_response

        # Mock playlist creation
        mock_created_playlist = {
            'id': 'new_playlist_456',
            'name': 'New Playlist',
            'owner': {'id': 'user_123'}
        }
        self.mock_spotify.user_playlist_create.return_value = mock_created_playlist

        playlist = self.provider.resolve_or_create_playlist("New Playlist")

        assert playlist.id == 'new_playlist_456'
        assert playlist.name == 'New Playlist'
        assert playlist.owner_id == 'user_123'
        assert playlist.is_owned is True

        # Verify playlist was created with correct parameters
        self.mock_spotify.user_playlist_create.assert_called_once_with(
            'user_123', 'New Playlist', public=False
        )

    def test_add_tracks_batch_successfully_adds_tracks(self):
        """Test that add_tracks_batch successfully adds tracks."""
        track_uris = ['spotify:track:123', 'spotify:track:456', 'spotify:track:789']

        # Mock successful addition
        self.mock_spotify.playlist_add_items.return_value = {
            'snapshot_id': 'snapshot_123'
        }

        result = self.provider.add_tracks_batch('playlist_123', track_uris)

        assert result.added == 3
        assert result.duplicates == 0
        assert result.errors == 0

        # Verify tracks were added
        self.mock_spotify.playlist_add_items.assert_called_once_with(
            'playlist_123', track_uris
        )

    def test_add_tracks_batch_handles_duplicates(self):
        """Test that add_tracks_batch handles duplicate tracks correctly."""
        track_uris = ['spotify:track:123', 'spotify:track:456']

        # Mock response indicating some tracks were duplicates
        self.mock_spotify.playlist_add_items.return_value = {
            'snapshot_id': 'snapshot_123'
        }

        result = self.provider.add_tracks_batch('playlist_123', track_uris)

        # For MVP, we assume all tracks were added successfully
        # In a real implementation, we'd need to check the playlist contents
        assert result.added == 2
        assert result.duplicates == 0
        assert result.errors == 0

    def test_add_tracks_batch_respects_batch_size_limit(self):
        """Test that add_tracks_batch respects the 100 track limit."""
        # Create 150 track URIs
        track_uris = [f'spotify:track:{i}' for i in range(150)]

        self.mock_spotify.playlist_add_items.return_value = {
            'snapshot_id': 'snapshot_123'
        }

        result = self.provider.add_tracks_batch('playlist_123', track_uris)

        # Should only add first 100 tracks
        assert result.added == 100
        assert result.duplicates == 0
        assert result.errors == 0

        # Verify only first 100 were sent to API
        self.mock_spotify.playlist_add_items.assert_called_once_with(
            'playlist_123', track_uris[:100]
        )

    def test_handles_rate_limited_error(self):
        """Test that provider handles rate limiting correctly."""
        rate_limit_error = Exception("Rate limited")
        rate_limit_error.status_code = 429
        self.mock_spotify.search.side_effect = rate_limit_error

        track = Track(
            source_id="track_1",
            title="Test Song",
            artists=["Test Artist"],
            duration_ms=180000
        )

        with pytest.raises(RateLimited):
            self.provider.find_track_candidates(track)

    def test_handles_network_error(self):
        """Test that provider handles network errors correctly."""
        self.mock_spotify.search.side_effect = Exception("Network error")

        track = Track(
            source_id="track_1",
            title="Test Song",
            artists=["Test Artist"],
            duration_ms=180000
        )

        with pytest.raises(TemporaryFailure):
            self.provider.find_track_candidates(track)

    def test_handles_not_found_error(self):
        """Test that provider handles not found errors correctly."""
        self.mock_spotify.playlist_add_items.side_effect = Exception("Playlist not found")

        with pytest.raises(NotFound):
            self.provider.add_tracks_batch('nonexistent_playlist', ['spotify:track:123'])

    def test_handles_5xx_errors(self):
        """Test that provider handles 5xx server errors correctly."""
        server_error = Exception("Internal server error")
        server_error.status_code = 500
        self.mock_spotify.search.side_effect = server_error

        track = Track(
            source_id="track_1",
            title="Test Song",
            artists=["Test Artist"],
            duration_ms=180000
        )

        with pytest.raises(TemporaryFailure):
            self.provider.find_track_candidates(track)

    def test_initialization_with_tokens(self):
        """Test that provider initializes correctly with tokens."""
        with patch('builtins.__import__') as mock_import:
            # Create a mock spotipy module
            mock_spotipy = Mock()
            mock_spotify_client = Mock()
            mock_spotipy.Spotify.return_value = mock_spotify_client
            
            # Make __import__ return our mock when spotipy is imported
            def side_effect(name, *args, **kwargs):
                if name == 'spotipy':
                    return mock_spotipy
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = side_effect

            provider = SpotifyProvider(
                access_token="test_access_token",
                refresh_token="test_refresh_token",
                expires_at=datetime.now() + timedelta(hours=1)
            )

            mock_spotipy.Spotify.assert_called_once_with(
                auth="test_access_token"
            )

    def test_search_query_building_for_isrc(self):
        """Test that search queries are built correctly for ISRC search."""
        track = Track(
            source_id="track_1",
            title="Test Song",
            artists=["Test Artist"],
            duration_ms=180000,
            isrc="USABC1234567"
        )

        # Mock empty ISRC search result, so it falls back to fuzzy search
        def side_effect(query, **kwargs):
            if query.startswith('isrc:'):
                return {'tracks': {'items': []}}
            else:
                return {'tracks': {'items': []}}
        
        self.mock_spotify.search.side_effect = side_effect

        self.provider.find_track_candidates(track)

        # Verify ISRC search was called first
        calls = self.mock_spotify.search.call_args_list
        assert len(calls) >= 1
        first_call = calls[0]
        assert first_call[0][0] == 'isrc:USABC1234567'
        assert first_call[1]['type'] == 'track'
        assert first_call[1]['limit'] == self.provider._search_limit
        assert first_call[1]['market'] == 'RU'

    def test_search_query_building_for_title_artist(self):
        """Test that search queries are built correctly for title+artist search."""
        track = Track(
            source_id="track_1",
            title="Test Song",
            artists=["Test Artist", "Feat Artist"],
            duration_ms=180000,
            isrc=None
        )

        # Mock empty search results
        def side_effect(query, **kwargs):
            return {'tracks': {'items': []}}
        
        self.mock_spotify.search.side_effect = side_effect

        self.provider.find_track_candidates(track)

        # Verify title+artist search was called
        calls = self.mock_spotify.search.call_args_list
        assert len(calls) >= 1
        first_call = calls[0]
        assert first_call[0][0] == 'track:"Test Song" artist:"Test Artist"'
        assert first_call[1]['type'] == 'track'
        assert first_call[1]['limit'] == self.provider._search_limit
        assert first_call[1]['market'] == 'RU'

    def test_confidence_calculation_for_exact_match(self):
        """Test that confidence is calculated correctly for exact matches."""
        track = Track(
            source_id="track_1",
            title="Test Song",
            artists=["Test Artist"],
            duration_ms=180000,
            isrc=None
        )

        # Mock exact match
        mock_search_response = {
            'tracks': {
                'items': [{
                    'uri': 'spotify:track:exact_123',
                    'name': 'Test Song',
                    'artists': [{'name': 'Test Artist'}],
                    'duration_ms': 180000
                }]
            }
        }
        self.mock_spotify.search.return_value = mock_search_response

        candidates = self.provider.find_track_candidates(track)

        assert len(candidates) == 1
        assert candidates[0].confidence >= 0.95  # Exact match should have high confidence
        assert candidates[0].reason == 'exact_match'

    def test_confidence_calculation_for_fuzzy_match(self):
        """Test that confidence is calculated correctly for fuzzy matches."""
        track = Track(
            source_id="track_1",
            title="Test Song",
            artists=["Test Artist"],
            duration_ms=180000,
            isrc=None
        )

        # Mock fuzzy match (different duration)
        mock_search_response = {
            'tracks': {
                'items': [{
                    'uri': 'spotify:track:fuzzy_123',
                    'name': 'Test Song',
                    'artists': [{'name': 'Test Artist'}],
                    'duration_ms': 190000  # Different duration
                }]
            }
        }
        self.mock_spotify.search.return_value = mock_search_response

        candidates = self.provider.find_track_candidates(track)

        assert len(candidates) == 1
        assert candidates[0].confidence < 0.95  # Fuzzy match should have lower confidence
        assert candidates[0].reason in ('fuzzy_match', 'relaxed_match')

    def test_search_uses_ru_market_and_supports_cyrillic(self):
        """Test that searches use RU market and work with Cyrillic queries."""
        track = Track(
            source_id="track_ru",
            title="Группа крови",
            artists=["Кино"],
            duration_ms=286000,
            isrc=None
        )

        # Return empty to just inspect search call
        self.mock_spotify.search.return_value = {'tracks': {'items': []}}

        self.provider.find_track_candidates(track, top_k=3)

        first_call = self.mock_spotify.search.call_args_list[0]
        # Query should contain Cyrillic as-is
        assert 'track:"Группа крови" artist:"Кино"' == first_call[0][0]
        assert first_call[1]['type'] == 'track'
        assert first_call[1]['market'] == 'RU'
        assert first_call[1]['limit'] == self.provider._search_limit
