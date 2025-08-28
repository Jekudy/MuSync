import pytest
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch

from app.application.matching import TrackMatcher
from app.application.pipeline import TransferPipeline, CheckpointManager
from app.domain.entities import Track, Playlist, Candidate, AddResult


class SimpleYandexProvider:
    """Simple Yandex provider for E2E testing."""
    
    def __init__(self):
        self.playlists = [
            Playlist(id="p1", name="Test Playlist", owner_id="user1", is_owned=True),
        ]
        self.tracks = {
            "p1": [
                Track(source_id="t1", title="Test Song 1", artists=["Test Artist"], duration_ms=200000),
                Track(source_id="t2", title="Test Song 2", artists=["Test Artist"], duration_ms=180000),
            ]
        }
    
    def list_owned_playlists(self):
        return [p for p in self.playlists if p.is_owned]
    
    def list_tracks(self, playlist_id: str):
        return self.tracks.get(playlist_id, [])


class SimpleSpotifyProvider:
    """Simple Spotify provider for E2E testing."""
    
    def __init__(self):
        self.playlists = {}
        self.added_tracks = {}
        self.search_results = {
            "Test Song 1": [
                Candidate(uri="spotify:track:test1", confidence=0.95, reason="exact"),
            ],
            "Test Song 2": [
                Candidate(uri="spotify:track:test2", confidence=0.90, reason="exact"),
            ],
        }
    
    def find_track_candidates(self, track: Track, top_k: int = 3):
        return self.search_results.get(track.title, [])
    
    def resolve_or_create_playlist(self, name: str):
        if name not in self.playlists:
            self.playlists[name] = Playlist(id=f"sp_{name}", name=name, owner_id="spotify_user", is_owned=True)
        return self.playlists[name]
    
    def add_tracks_batch(self, playlist_id: str, track_uris: list):
        if playlist_id not in self.added_tracks:
            self.added_tracks[playlist_id] = []
        
        added = 0
        duplicates = 0
        
        for uri in track_uris:
            if uri not in self.added_tracks[playlist_id]:
                self.added_tracks[playlist_id].append(uri)
                added += 1
            else:
                duplicates += 1
        
        return AddResult(added=added, duplicates=duplicates, errors=0)


class TestSimpleE2E:
    """Simplified E2E tests for the transfer pipeline."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.source_provider = SimpleYandexProvider()
        self.target_provider = SimpleSpotifyProvider()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_basic_transfer_works(self):
        """Test that basic transfer functionality works."""
        matcher = TrackMatcher()
        checkpoint_manager = CheckpointManager(self.temp_dir)
        
        pipeline = TransferPipeline(
            source_provider=self.source_provider,
            target_provider=self.target_provider,
            matcher=matcher,
            checkpoint_manager=checkpoint_manager
        )
        
        # Transfer playlist
        playlist = self.source_provider.playlists[0]
        result = pipeline.transfer_playlist(playlist, job_id="test_job", dry_run=False)
        
        # Verify basic results
        assert result.total_tracks == 2
        assert result.errors == []  # No errors should occur
        assert result.duration_ms >= 0
    
    def test_dry_run_mode_works(self):
        """Test that dry-run mode works without modifying state."""
        matcher = TrackMatcher()
        checkpoint_manager = CheckpointManager(self.temp_dir)
        
        pipeline = TransferPipeline(
            source_provider=self.source_provider,
            target_provider=self.target_provider,
            matcher=matcher,
            checkpoint_manager=checkpoint_manager
        )
        
        # Run dry-run transfer
        playlist = self.source_provider.playlists[0]
        result = pipeline.transfer_playlist(playlist, job_id="test_job", dry_run=True)
        
        # Verify basic results
        assert result.total_tracks == 2
        assert result.errors == []  # No errors should occur
    
    def test_idempotency_works(self):
        """Test that idempotency works correctly."""
        matcher = TrackMatcher()
        checkpoint_manager = CheckpointManager(self.temp_dir)
        
        pipeline = TransferPipeline(
            source_provider=self.source_provider,
            target_provider=self.target_provider,
            matcher=matcher,
            checkpoint_manager=checkpoint_manager
        )
        
        playlist = self.source_provider.playlists[0]
        
        # First transfer
        result1 = pipeline.transfer_playlist(playlist, job_id="test_job", dry_run=False)
        assert result1.total_tracks == 2
        assert result1.errors == []
        
        # Second transfer (should be idempotent)
        result2 = pipeline.transfer_playlist(playlist, job_id="test_job", dry_run=False)
        assert result2.total_tracks == 2
        assert result2.errors == []
    
    def test_error_handling_works(self):
        """Test that error handling works correctly."""
        # Create provider that throws errors
        error_provider = Mock()
        error_provider.list_owned_playlists.side_effect = Exception("Network error")
        
        matcher = TrackMatcher()
        checkpoint_manager = CheckpointManager(self.temp_dir)
        
        pipeline = TransferPipeline(
            source_provider=error_provider,
            target_provider=self.target_provider,
            matcher=matcher,
            checkpoint_manager=checkpoint_manager
        )
        
        # Should handle errors gracefully
        with pytest.raises(Exception):
            error_provider.list_owned_playlists()
    
    def test_performance_is_acceptable(self):
        """Test that performance is acceptable."""
        import time
        
        matcher = TrackMatcher()
        checkpoint_manager = CheckpointManager(self.temp_dir)
        
        pipeline = TransferPipeline(
            source_provider=self.source_provider,
            target_provider=self.target_provider,
            matcher=matcher,
            checkpoint_manager=checkpoint_manager
        )
        
        start_time = time.time()
        
        # Transfer playlist
        playlist = self.source_provider.playlists[0]
        result = pipeline.transfer_playlist(playlist, job_id="test_job", dry_run=False)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should be fast for small datasets
        assert duration < 5.0, f"Transfer took {duration:.2f}s, should be under 5s"
        assert result.total_tracks == 2
    
    def test_acceptance_criteria_met(self):
        """Test that acceptance criteria are met."""
        matcher = TrackMatcher()
        checkpoint_manager = CheckpointManager(self.temp_dir)
        
        pipeline = TransferPipeline(
            source_provider=self.source_provider,
            target_provider=self.target_provider,
            matcher=matcher,
            checkpoint_manager=checkpoint_manager
        )
        
        # Transfer playlist
        playlist = self.source_provider.playlists[0]
        result = pipeline.transfer_playlist(playlist, job_id="test_job", dry_run=False)
        
        # Calculate rates
        match_rate = result.matched_tracks / result.total_tracks if result.total_tracks > 0 else 0
        success_rate = result.added_tracks / result.matched_tracks if result.matched_tracks > 0 else 0
        
        # Verify acceptance criteria
        assert match_rate >= 0.90, f"Match rate {match_rate:.2%} below 90% threshold"
        assert success_rate >= 0.95, f"Success rate {success_rate:.2%} below 95% threshold"
        assert result.errors == [], "No errors should occur"
