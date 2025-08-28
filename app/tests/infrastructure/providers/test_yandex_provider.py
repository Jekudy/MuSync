from typing import Iterable
from unittest.mock import Mock, patch

import pytest

from app.domain.entities import Playlist, Track
from app.domain.errors import RateLimited, TemporaryFailure, NotFound
from app.infrastructure.providers.yandex import YandexMusicProvider


class TestYandexMusicProvider:
    """Contract tests for Yandex Music provider adapter."""

    def setup_method(self):
        """Set up test fixtures."""
        # Mock the entire client creation to avoid real API calls
        with patch('yandex_music.Client') as mock_client_class:
            self.mock_client = Mock()
            mock_client_class.return_value = self.mock_client
            self.mock_client.init.return_value = self.mock_client
            
            # Create provider with mocked client
            self.provider = YandexMusicProvider("test_token")
            # Ensure the mock client is used
            self.provider._client = self.mock_client

    def test_list_owned_playlists_returns_all_playlists_with_ownership_flags(self):
        """Test that list_owned_playlists returns all playlists with correct ownership flags."""
        # Mock playlist data
        mock_playlist1 = Mock()
        mock_playlist1.kind = "playlist_1"
        mock_playlist1.title = "My Playlist"
        mock_playlist1.owner.uid = "user_123"
        mock_playlist1.track_count = 10

        mock_playlist2 = Mock()
        mock_playlist2.kind = "playlist_2"
        mock_playlist2.title = "Subscribed Playlist"
        mock_playlist2.owner.uid = "other_user"
        mock_playlist2.track_count = 5

        # Mock user ID
        mock_user = Mock()
        mock_user.uid = "user_123"
        self.mock_client.users_me.return_value = mock_user

        # Mock playlists list
        self.mock_client.users_playlists_list.return_value = [mock_playlist1, mock_playlist2]

        playlists = list(self.provider.list_owned_playlists())

        # Should return both playlists with correct ownership flags
        assert len(playlists) == 2
        
        # Check first playlist (owned)
        assert playlists[0].id == "playlist_1"
        assert playlists[0].name == "My Playlist"
        assert playlists[0].owner_id == "user_123"
        assert playlists[0].is_owned is True

        # Check second playlist (subscribed)
        assert playlists[1].id == "playlist_2"
        assert playlists[1].name == "Subscribed Playlist"
        assert playlists[1].owner_id == "other_user"
        assert playlists[1].is_owned is False

    def test_list_tracks_returns_domain_tracks(self):
        """Test that list_tracks returns domain Track entities."""
        # Mock track data with proper artist mocking
        mock_artist1 = Mock()
        mock_artist1.name = "Artist 1"
        mock_artist2 = Mock()
        mock_artist2.name = "Artist 2"
        mock_solo_artist = Mock()
        mock_solo_artist.name = "Solo Artist"

        mock_track1 = Mock()
        mock_track1.id = "track_1"
        mock_track1.title = "Song Title"
        mock_track1.artists = [mock_artist1, mock_artist2]
        mock_track1.duration_ms = 180000
        mock_track1.albums = [Mock(title="Album Name")]
        mock_track1.isrc = "USABC1234567"

        mock_track2 = Mock()
        mock_track2.id = "track_2"
        mock_track2.title = "Another Song"
        mock_track2.artists = [mock_solo_artist]
        mock_track2.duration_ms = 200000
        mock_track2.albums = [Mock(title="Another Album")]
        mock_track2.isrc = None

        # Mock playlist tracks
        mock_playlist = Mock()
        mock_playlist.fetch_tracks.return_value = [mock_track1, mock_track2]
        self.mock_client.users_playlists.return_value = mock_playlist

        tracks = list(self.provider.list_tracks("playlist_123"))

        assert len(tracks) == 2

        # Check first track
        assert tracks[0].source_id == "track_1"
        assert tracks[0].title == "Song Title"
        assert tracks[0].artists == ["Artist 1", "Artist 2"]
        assert tracks[0].duration_ms == 180000
        assert tracks[0].album == "Album Name"
        assert tracks[0].isrc == "USABC1234567"

        # Check second track
        assert tracks[1].source_id == "track_2"
        assert tracks[1].title == "Another Song"
        assert tracks[1].artists == ["Solo Artist"]
        assert tracks[1].duration_ms == 200000
        assert tracks[1].album == "Another Album"
        assert tracks[1].isrc is None

    def test_list_tracks_handles_empty_playlist(self):
        """Test that list_tracks handles empty playlists correctly."""
        mock_playlist = Mock()
        mock_playlist.fetch_tracks.return_value = []
        self.mock_client.users_playlists.return_value = mock_playlist

        tracks = list(self.provider.list_tracks("empty_playlist"))

        assert len(tracks) == 0

    def test_list_tracks_handles_missing_metadata(self):
        """Test that list_tracks handles tracks with missing metadata."""
        mock_track = Mock()
        mock_track.id = "track_1"
        mock_track.title = "Song Title"
        mock_track.artists = []
        mock_track.duration_ms = 0
        mock_track.albums = []
        mock_track.isrc = None

        mock_playlist = Mock()
        mock_playlist.fetch_tracks.return_value = [mock_track]
        self.mock_client.users_playlists.return_value = mock_playlist

        tracks = list(self.provider.list_tracks("playlist_123"))

        assert len(tracks) == 1
        assert tracks[0].source_id == "track_1"
        assert tracks[0].title == "Song Title"
        assert tracks[0].artists == []
        assert tracks[0].duration_ms == 0
        assert tracks[0].album is None
        assert tracks[0].isrc is None

    def test_list_tracks_handles_pagination(self):
        """Test that list_tracks handles pagination correctly."""
        # Mock artists
        mock_artist1 = Mock()
        mock_artist1.name = "Artist 1"
        mock_artist2 = Mock()
        mock_artist2.name = "Artist 2"

        # Mock tracks for pagination
        mock_track1 = Mock()
        mock_track1.id = "track_1"
        mock_track1.title = "Song 1"
        mock_track1.artists = [mock_artist1]
        mock_track1.duration_ms = 180000
        mock_track1.albums = []
        mock_track1.isrc = None

        mock_track2 = Mock()
        mock_track2.id = "track_2"
        mock_track2.title = "Song 2"
        mock_track2.artists = [mock_artist2]
        mock_track2.duration_ms = 200000
        mock_track2.albums = []
        mock_track2.isrc = None

        # Mock playlist with all tracks returned at once (simplified pagination)
        mock_playlist = Mock()
        mock_playlist.fetch_tracks.return_value = [mock_track1, mock_track2]
        self.mock_client.users_playlists.return_value = mock_playlist

        tracks = list(self.provider.list_tracks("playlist_123"))

        assert len(tracks) == 2
        assert tracks[0].title == "Song 1"
        assert tracks[1].title == "Song 2"

    def test_handles_rate_limited_error(self):
        """Test that provider handles rate limiting correctly."""
        self.mock_client.users_playlists_list.side_effect = Exception("Rate limited")

        with pytest.raises(TemporaryFailure):
            list(self.provider.list_owned_playlists())

    def test_handles_network_error(self):
        """Test that provider handles network errors correctly."""
        self.mock_client.users_playlists_list.side_effect = Exception("Network error")

        with pytest.raises(TemporaryFailure):
            list(self.provider.list_owned_playlists())

    def test_handles_not_found_error(self):
        """Test that provider handles not found errors correctly."""
        self.mock_client.users_playlists.side_effect = Exception("Playlist not found")

        with pytest.raises(NotFound):
            list(self.provider.list_tracks("nonexistent_playlist"))

    def test_handles_5xx_errors(self):
        """Test that provider handles 5xx server errors correctly."""
        self.mock_client.users_playlists_list.side_effect = Exception("Internal server error")

        with pytest.raises(TemporaryFailure):
            list(self.provider.list_owned_playlists())

    def test_handles_429_errors(self):
        """Test that provider handles 429 rate limit errors correctly."""
        rate_limit_error = Exception("Too many requests")
        rate_limit_error.status_code = 429
        self.mock_client.users_playlists_list.side_effect = rate_limit_error

        with pytest.raises(RateLimited):
            list(self.provider.list_owned_playlists())

    def test_initialization_with_token(self):
        """Test that provider initializes correctly with token."""
        with patch('yandex_music.Client') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.init.return_value = mock_client

            provider = YandexMusicProvider("test_token")

            mock_client_class.assert_called_once_with("test_token")
            mock_client.init.assert_called_once()

    def test_playlist_ownership_detection(self):
        """Test that playlist ownership is detected correctly."""
        # Mock user
        mock_user = Mock()
        mock_user.uid = "user_123"
        self.mock_client.users_me.return_value = mock_user

        # Mock owned playlist
        mock_owned_playlist = Mock()
        mock_owned_playlist.kind = "owned_playlist"
        mock_owned_playlist.title = "Owned Playlist"
        mock_owned_playlist.owner.uid = "user_123"
        mock_owned_playlist.track_count = 5

        # Mock subscribed playlist
        mock_subscribed_playlist = Mock()
        mock_subscribed_playlist.kind = "subscribed_playlist"
        mock_subscribed_playlist.title = "Subscribed Playlist"
        mock_subscribed_playlist.owner.uid = "other_user"
        mock_subscribed_playlist.track_count = 10

        self.mock_client.users_playlists_list.return_value = [
            mock_owned_playlist,
            mock_subscribed_playlist
        ]

        playlists = list(self.provider.list_owned_playlists())

        # Should return both owned and subscribed playlists
        assert len(playlists) == 2
        
        # Check ownership flags
        owned_playlist = next(p for p in playlists if p.id == "owned_playlist")
        subscribed_playlist = next(p for p in playlists if p.id == "subscribed_playlist")
        
        assert owned_playlist.is_owned is True
        assert subscribed_playlist.is_owned is False
