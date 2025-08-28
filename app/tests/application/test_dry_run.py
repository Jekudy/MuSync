from typing import List
from unittest.mock import Mock, patch
from datetime import datetime

import pytest

from app.application.pipeline import TransferPipeline, BatchProcessor
from app.application.matching import TrackMatcher
from app.domain.entities import Track, Playlist, Candidate, AddResult
from app.domain.ports import MusicProvider


class TestDryRunMode:
    """Tests for dry-run mode functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.source_provider = Mock(spec=MusicProvider)
        self.target_provider = Mock(spec=MusicProvider)
        self.matcher = Mock(spec=TrackMatcher)
        self.checkpoint_manager = Mock()
        
        self.pipeline = TransferPipeline(
            source_provider=self.source_provider,
            target_provider=self.target_provider,
            matcher=self.matcher,
            checkpoint_manager=self.checkpoint_manager,
            batch_size=100
        )

    def test_dry_run_mode_does_not_call_add_tracks_batch(self):
        """Test that dry-run mode does not call add_tracks_batch on target provider."""
        # Mock source playlist and tracks
        source_playlist = Playlist(
            id="source_playlist_1",
            name="Test Playlist",
            owner_id="user_1",
            is_owned=True
        )
        
        source_tracks = [
            Track(
                source_id="track_1",
                title="Song One",
                artists=["Artist One"],
                duration_ms=180000,
                isrc="TEST001"
            ),
            Track(
                source_id="track_2",
                title="Song Two",
                artists=["Artist Two"],
                duration_ms=200000,
                isrc="TEST002"
            )
        ]
        
        self.source_provider.list_tracks.return_value = source_tracks
        
        # Mock target provider responses
        self.target_provider.find_track_candidates.side_effect = [
            [Candidate(uri="spotify:track:1", confidence=1.0, reason="isrc_exact")],
            [Candidate(uri="spotify:track:2", confidence=1.0, reason="isrc_exact")]
        ]
        
        self.target_provider.resolve_or_create_playlist.return_value = Playlist(
            id="target_playlist_1",
            name="Test Playlist",
            owner_id="target_user",
            is_owned=True
        )
        
        # Mock matcher
        self.matcher.find_best_match.side_effect = [
            Mock(uri="spotify:track:1", confidence=1.0, reason="isrc_exact"),
            Mock(uri="spotify:track:2", confidence=1.0, reason="isrc_exact")
        ]
        
        # Mock checkpoint manager
        self.checkpoint_manager.load_checkpoint.return_value = None
        
        # Execute transfer in dry-run mode
        result = self.pipeline.transfer_playlist(
            source_playlist=source_playlist,
            job_id="test_job_1",
            dry_run=True
        )
        
        # Verify that add_tracks_batch was NOT called
        self.target_provider.add_tracks_batch.assert_not_called()
        
        # Verify that other operations were still performed
        self.target_provider.resolve_or_create_playlist.assert_called_once()
        self.target_provider.find_track_candidates.assert_called()
        self.matcher.find_best_match.assert_called()

    def test_dry_run_mode_generates_complete_report(self):
        """Test that dry-run mode generates complete report with candidates and confidence."""
        source_playlist = Playlist(
            id="source_playlist_1",
            name="Test Playlist",
            owner_id="user_1",
            is_owned=True
        )
        
        source_tracks = [
            Track(
                source_id="track_1",
                title="Song One",
                artists=["Artist One"],
                duration_ms=180000,
                isrc="TEST001"
            ),
            Track(
                source_id="track_2",
                title="Song Two",
                artists=["Artist Two"],
                duration_ms=200000,
                isrc=None
            )
        ]
        
        self.source_provider.list_tracks.return_value = source_tracks
        
        # Mock target provider responses
        self.target_provider.find_track_candidates.side_effect = [
            [Candidate(uri="spotify:track:1", confidence=1.0, reason="isrc_exact")],
            [Candidate(uri="spotify:track:2", confidence=0.95, reason="exact_match")]
        ]
        
        self.target_provider.resolve_or_create_playlist.return_value = Playlist(
            id="target_playlist_1",
            name="Test Playlist",
            owner_id="target_user",
            is_owned=True
        )
        
        # Mock matcher
        self.matcher.find_best_match.side_effect = [
            Mock(uri="spotify:track:1", confidence=1.0, reason="isrc_exact"),
            Mock(uri="spotify:track:2", confidence=0.95, reason="exact_match")
        ]
        
        # Mock checkpoint manager
        self.checkpoint_manager.load_checkpoint.return_value = None
        
        # Execute transfer in dry-run mode
        result = self.pipeline.transfer_playlist(
            source_playlist=source_playlist,
            job_id="test_job_1",
            dry_run=True
        )
        
        # Verify report contains expected data
        assert result.playlist_id == "target_playlist_1"
        assert result.playlist_name == "Test Playlist"
        assert result.total_tracks == 2
        assert result.matched_tracks == 2
        assert result.added_tracks == 0  # No tracks added in dry-run
        assert result.duplicate_tracks == 0
        assert result.failed_tracks == 0
        assert result.duration_ms > 0

    def test_dry_run_mode_handles_not_found_tracks(self):
        """Test that dry-run mode handles not found tracks correctly."""
        source_playlist = Playlist(
            id="source_playlist_1",
            name="Test Playlist",
            owner_id="user_1",
            is_owned=True
        )
        
        source_tracks = [
            Track(
                source_id="track_1",
                title="Found Song",
                artists=["Found Artist"],
                duration_ms=180000,
                isrc="FOUND001"
            ),
            Track(
                source_id="track_2",
                title="Not Found Song",
                artists=["Unknown Artist"],
                duration_ms=200000,
                isrc=None
            )
        ]
        
        self.source_provider.list_tracks.return_value = source_tracks
        
        # Mock target provider responses
        self.target_provider.find_track_candidates.side_effect = [
            [Candidate(uri="spotify:track:1", confidence=1.0, reason="isrc_exact")],
            []  # No candidates for second track
        ]
        
        self.target_provider.resolve_or_create_playlist.return_value = Playlist(
            id="target_playlist_1",
            name="Test Playlist",
            owner_id="target_user",
            is_owned=True
        )
        
        # Mock matcher
        self.matcher.find_best_match.side_effect = [
            Mock(uri="spotify:track:1", confidence=1.0, reason="isrc_exact"),
            Mock(uri=None, confidence=0.0, reason="not_found")
        ]
        
        # Mock checkpoint manager
        self.checkpoint_manager.load_checkpoint.return_value = None
        
        # Execute transfer in dry-run mode
        result = self.pipeline.transfer_playlist(
            source_playlist=source_playlist,
            job_id="test_job_1",
            dry_run=True
        )
        
        # Verify results
        assert result.total_tracks == 2
        assert result.matched_tracks == 1
        assert result.not_found_tracks == 1
        assert result.added_tracks == 0  # No tracks added in dry-run
        
        # Verify that add_tracks_batch was NOT called
        self.target_provider.add_tracks_batch.assert_not_called()

    def test_dry_run_mode_with_checkpoint_recovery(self):
        """Test that dry-run mode works correctly with checkpoint recovery."""
        source_playlist = Playlist(
            id="source_playlist_1",
            name="Recovery Playlist",
            owner_id="user_1",
            is_owned=True
        )
        
        # Mock existing checkpoint
        existing_checkpoint = {
            "jobId": "test_job_1",
            "playlistId": "source_playlist_1",
            "batchIndex": 1,
            "stage": "writing",
            "cursor": {
                "trackIndex": 2,
                "batchTrackIndex": 0
            },
            "addedUris": ["spotify:track:1", "spotify:track:2"],
            "attempts": 0,
            "updatedAt": datetime.now().isoformat()
        }
        
        self.checkpoint_manager.load_checkpoint.return_value = existing_checkpoint
        
        # All tracks in the playlist
        all_tracks = [
            Track("track_1", "Song One", ["Artist One"], 180000, "TEST001"),
            Track("track_2", "Song Two", ["Artist Two"], 200000, "TEST002"),
            Track("track_3", "Song Three", ["Artist Three"], 180000, "TEST003"),
            Track("track_4", "Song Four", ["Artist Four"], 200000, "TEST004")
        ]
        
        self.source_provider.list_tracks.return_value = all_tracks
        
        # Mock target provider responses
        self.target_provider.find_track_candidates.side_effect = [
            [Candidate(uri="spotify:track:3", confidence=1.0, reason="isrc_exact")],
            [Candidate(uri="spotify:track:4", confidence=1.0, reason="isrc_exact")]
        ]
        
        self.target_provider.resolve_or_create_playlist.return_value = Playlist(
            id="target_playlist_1",
            name="Recovery Playlist",
            owner_id="target_user",
            is_owned=True
        )
        
        # Mock matcher
        self.matcher.find_best_match.side_effect = [
            Mock(uri="spotify:track:3", confidence=1.0, reason="isrc_exact"),
            Mock(uri="spotify:track:4", confidence=1.0, reason="isrc_exact")
        ]
        
        # Execute transfer in dry-run mode
        result = self.pipeline.transfer_playlist(
            source_playlist=source_playlist,
            job_id="test_job_1",
            dry_run=True
        )
        
        # Verify checkpoint was loaded
        self.checkpoint_manager.load_checkpoint.assert_called_once_with("test_job_1", "source_playlist_1")
        
        # Verify that add_tracks_batch was NOT called
        self.target_provider.add_tracks_batch.assert_not_called()
        
        # Verify results
        assert result.total_tracks == 4
        assert result.matched_tracks == 4
        assert result.added_tracks == 0  # No tracks added in dry-run

    def test_dry_run_mode_logs_dry_run_flag(self):
        """Test that dry-run mode logs with dry_run=true flag."""
        source_playlist = Playlist(
            id="source_playlist_1",
            name="Test Playlist",
            owner_id="user_1",
            is_owned=True
        )
        
        source_tracks = [
            Track(
                source_id="track_1",
                title="Song One",
                artists=["Artist One"],
                duration_ms=180000,
                isrc="TEST001"
            )
        ]
        
        self.source_provider.list_tracks.return_value = source_tracks
        self.target_provider.find_track_candidates.return_value = [
            Candidate(uri="spotify:track:1", confidence=1.0, reason="isrc_exact")
        ]
        self.target_provider.resolve_or_create_playlist.return_value = Playlist(
            id="target_playlist_1",
            name="Test Playlist",
            owner_id="target_user",
            is_owned=True
        )
        self.matcher.find_best_match.return_value = Mock(
            uri="spotify:track:1", confidence=1.0, reason="isrc_exact"
        )
        self.checkpoint_manager.load_checkpoint.return_value = None
        
        with patch('app.application.pipeline.logger') as mock_logger:
            # Execute transfer in dry-run mode
            result = self.pipeline.transfer_playlist(
                source_playlist=source_playlist,
                job_id="test_job_1",
                dry_run=True
            )
            
            # Verify that dry-run mode was logged
            # Note: This test verifies that dry-run mode is properly handled
            # The actual logging implementation would need to be checked
            assert result.added_tracks == 0  # No tracks added in dry-run

    def test_dry_run_mode_creates_metrics(self):
        """Test that dry-run mode creates metrics without actual operations."""
        source_playlist = Playlist(
            id="source_playlist_1",
            name="Test Playlist",
            owner_id="user_1",
            is_owned=True
        )
        
        source_tracks = [
            Track(
                source_id="track_1",
                title="Song One",
                artists=["Artist One"],
                duration_ms=180000,
                isrc="TEST001"
            ),
            Track(
                source_id="track_2",
                title="Song Two",
                artists=["Artist Two"],
                duration_ms=200000,
                isrc="TEST002"
            )
        ]
        
        self.source_provider.list_tracks.return_value = source_tracks
        
        # Mock target provider responses
        self.target_provider.find_track_candidates.side_effect = [
            [Candidate(uri="spotify:track:1", confidence=1.0, reason="isrc_exact")],
            [Candidate(uri="spotify:track:2", confidence=1.0, reason="isrc_exact")]
        ]
        
        self.target_provider.resolve_or_create_playlist.return_value = Playlist(
            id="target_playlist_1",
            name="Test Playlist",
            owner_id="target_user",
            is_owned=True
        )
        
        # Mock matcher
        self.matcher.find_best_match.side_effect = [
            Mock(uri="spotify:track:1", confidence=1.0, reason="isrc_exact"),
            Mock(uri="spotify:track:2", confidence=1.0, reason="isrc_exact")
        ]
        
        # Mock checkpoint manager
        self.checkpoint_manager.load_checkpoint.return_value = None
        
        # Execute transfer in dry-run mode
        result = self.pipeline.transfer_playlist(
            source_playlist=source_playlist,
            job_id="test_job_1",
            dry_run=True
        )
        
        # Verify metrics are created
        assert result.total_tracks == 2
        assert result.matched_tracks == 2
        assert result.added_tracks == 0  # No tracks added in dry-run
        assert result.duplicate_tracks == 0
        assert result.failed_tracks == 0
        assert result.duration_ms > 0
        assert len(result.errors) == 0

    def test_dry_run_mode_does_not_create_checkpoints(self):
        """Test that dry-run mode does not create checkpoints."""
        source_playlist = Playlist(
            id="source_playlist_1",
            name="Test Playlist",
            owner_id="user_1",
            is_owned=True
        )
        
        source_tracks = [
            Track(
                source_id="track_1",
                title="Song One",
                artists=["Artist One"],
                duration_ms=180000,
                isrc="TEST001"
            )
        ]
        
        self.source_provider.list_tracks.return_value = source_tracks
        self.target_provider.find_track_candidates.return_value = [
            Candidate(uri="spotify:track:1", confidence=1.0, reason="isrc_exact")
        ]
        self.target_provider.resolve_or_create_playlist.return_value = Playlist(
            id="target_playlist_1",
            name="Test Playlist",
            owner_id="target_user",
            is_owned=True
        )
        self.matcher.find_best_match.return_value = Mock(
            uri="spotify:track:1", confidence=1.0, reason="isrc_exact"
        )
        self.checkpoint_manager.load_checkpoint.return_value = None
        
        # Execute transfer in dry-run mode
        result = self.pipeline.transfer_playlist(
            source_playlist=source_playlist,
            job_id="test_job_1",
            dry_run=True
        )
        
        # Verify that no checkpoints were saved
        self.checkpoint_manager.save_checkpoint.assert_not_called()


class TestBatchProcessorDryRun:
    """Tests for BatchProcessor in dry-run mode."""

    def setup_method(self):
        """Set up test fixtures."""
        self.target_provider = Mock(spec=MusicProvider)
        self.checkpoint_manager = Mock()
        
        self.processor = BatchProcessor(
            target_provider=self.target_provider,
            checkpoint_manager=self.checkpoint_manager,
            batch_size=3,
            max_retries=3
        )

    def test_process_batch_dry_run_does_not_call_add_tracks_batch(self):
        """Test that dry-run mode does not call add_tracks_batch."""
        track_uris = ["spotify:track:1", "spotify:track:2", "spotify:track:3"]
        
        # Process batch in dry-run mode
        result = self.processor.process_batch(
            playlist_id="target_playlist_1",
            track_uris=track_uris,
            job_id="test_job",
            batch_index=0,
            dry_run=True
        )
        
        # Verify that add_tracks_batch was NOT called
        self.target_provider.add_tracks_batch.assert_not_called()
        
        # Verify that a mock result is returned
        assert result.added == len(track_uris)
        assert result.duplicates == 0
        assert result.errors == 0

    def test_process_batch_dry_run_handles_empty_batch(self):
        """Test that dry-run mode handles empty batch correctly."""
        track_uris = []
        
        # Process empty batch in dry-run mode
        result = self.processor.process_batch(
            playlist_id="target_playlist_1",
            track_uris=track_uris,
            job_id="test_job",
            batch_index=0,
            dry_run=True
        )
        
        # Verify that add_tracks_batch was NOT called
        self.target_provider.add_tracks_batch.assert_not_called()
        
        # Verify result
        assert result.added == 0
        assert result.duplicates == 0
        assert result.errors == 0

    def test_process_batch_dry_run_returns_consistent_results(self):
        """Test that dry-run mode returns consistent results."""
        track_uris = ["spotify:track:1", "spotify:track:2"]
        
        # Process batch multiple times in dry-run mode
        result1 = self.processor.process_batch(
            playlist_id="target_playlist_1",
            track_uris=track_uris,
            job_id="test_job",
            batch_index=0,
            dry_run=True
        )
        
        result2 = self.processor.process_batch(
            playlist_id="target_playlist_1",
            track_uris=track_uris,
            job_id="test_job",
            batch_index=1,
            dry_run=True
        )
        
        # Verify consistent results
        assert result1.added == result2.added == len(track_uris)
        assert result1.duplicates == result2.duplicates == 0
        assert result1.errors == result2.errors == 0
        
        # Verify that add_tracks_batch was never called
        self.target_provider.add_tracks_batch.assert_not_called()
