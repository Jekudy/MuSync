from typing import List
from unittest.mock import Mock, patch, call
from datetime import datetime, timedelta
import tempfile
import os
import json

import pytest

from app.application.pipeline import TransferPipeline, BatchProcessor, CheckpointManager
from app.application.matching import TrackMatcher, MatchResult
from app.domain.entities import Track, Candidate, Playlist, AddResult
from app.domain.errors import RateLimited, TemporaryFailure, NotFound
from app.infrastructure.providers.spotify import SpotifyProvider


class TestTransferPipeline:
    """Tests for the main transfer pipeline."""

    def setup_method(self):
        """Set up test fixtures."""
        self.source_provider = Mock()
        self.target_provider = Mock()
        self.matcher = Mock(spec=TrackMatcher)
        self.checkpoint_manager = Mock(spec=CheckpointManager)
        
        self.pipeline = TransferPipeline(
            source_provider=self.source_provider,
            target_provider=self.target_provider,
            matcher=self.matcher,
            checkpoint_manager=self.checkpoint_manager,
            batch_size=100
        )

    def test_transfer_playlist_success(self):
        """Test successful playlist transfer."""
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
        
        self.target_provider.add_tracks_batch.return_value = AddResult(
            added=2,
            duplicates=0,
            errors=0
        )
        
        # Mock matcher
        self.matcher.find_best_match.side_effect = [
            MatchResult(uri="spotify:track:1", confidence=1.0, reason="isrc_exact"),
            MatchResult(uri="spotify:track:2", confidence=1.0, reason="isrc_exact")
        ]
        
        # Mock checkpoint manager
        self.checkpoint_manager.load_checkpoint.return_value = None
        
        # Execute transfer
        result = self.pipeline.transfer_playlist(
            source_playlist=source_playlist,
            job_id="test_job_1"
        )
        
        # Verify results
        assert result.playlist_id == "target_playlist_1"
        assert result.total_tracks == 2
        assert result.matched_tracks == 2
        assert result.added_tracks == 2
        assert result.duplicate_tracks == 0
        assert result.failed_tracks == 0
        
        # Verify target provider calls
        self.target_provider.resolve_or_create_playlist.assert_called_once_with("Test Playlist")
        self.target_provider.add_tracks_batch.assert_called_once_with(
            "target_playlist_1",
            ["spotify:track:1", "spotify:track:2"]
        )

    def test_transfer_playlist_with_batching(self):
        """Test playlist transfer with large number of tracks requiring batching."""
        # Create a pipeline with small batch size for testing
        pipeline = TransferPipeline(
            source_provider=self.source_provider,
            target_provider=self.target_provider,
            matcher=self.matcher,
            checkpoint_manager=self.checkpoint_manager,
            batch_size=2  # Small batch for testing
        )
        
        source_playlist = Playlist(
            id="source_playlist_1",
            name="Large Playlist",
            owner_id="user_1",
            is_owned=True
        )
        
        # Create 5 tracks (requires 3 batches: 2+2+1)
        source_tracks = [
            Track(f"track_{i}", f"Song {i}", [f"Artist {i}"], 180000, f"TEST{i:03d}")
            for i in range(1, 6)
        ]
        
        self.source_provider.list_tracks.return_value = source_tracks
        
        # Mock target provider responses
        self.target_provider.find_track_candidates.side_effect = [
            [Candidate(uri=f"spotify:track:{i}", confidence=1.0, reason="isrc_exact")]
            for i in range(1, 6)
        ]
        
        self.target_provider.resolve_or_create_playlist.return_value = Playlist(
            id="target_playlist_1",
            name="Large Playlist",
            owner_id="target_user",
            is_owned=True
        )
        
        # Mock batch additions
        self.target_provider.add_tracks_batch.side_effect = [
            AddResult(added=2, duplicates=0, errors=0),  # Batch 1
            AddResult(added=2, duplicates=0, errors=0),  # Batch 2
            AddResult(added=1, duplicates=0, errors=0),  # Batch 3
        ]
        
        # Mock matcher
        self.matcher.find_best_match.side_effect = [
            MatchResult(uri=f"spotify:track:{i}", confidence=1.0, reason="isrc_exact")
            for i in range(1, 6)
        ]
        
        # Mock checkpoint manager
        self.checkpoint_manager.load_checkpoint.return_value = None
        
        # Execute transfer
        result = pipeline.transfer_playlist(
            source_playlist=source_playlist,
            job_id="test_job_1"
        )
        
        # Verify results
        assert result.total_tracks == 5
        assert result.matched_tracks == 5
        assert result.added_tracks == 5
        
        # Verify batching: should have 3 calls to add_tracks_batch
        assert self.target_provider.add_tracks_batch.call_count == 3
        expected_calls = [
            call("target_playlist_1", ["spotify:track:1", "spotify:track:2"]),
            call("target_playlist_1", ["spotify:track:3", "spotify:track:4"]),
            call("target_playlist_1", ["spotify:track:5"])
        ]
        self.target_provider.add_tracks_batch.assert_has_calls(expected_calls)

    def test_transfer_playlist_with_checkpoint_recovery(self):
        """Test playlist transfer with checkpoint recovery."""
        source_playlist = Playlist(
            id="source_playlist_1",
            name="Recovery Playlist",
            owner_id="user_1",
            is_owned=True
        )
        
        # Mock existing checkpoint (already processed 2 tracks)
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
        
        # All tracks in the playlist (including already processed ones)
        all_tracks = [
            Track("track_1", "Song One", ["Artist One"], 180000, "TEST001"),
            Track("track_2", "Song Two", ["Artist Two"], 200000, "TEST002"),
            Track("track_3", "Song Three", ["Artist Three"], 180000, "TEST003"),
            Track("track_4", "Song Four", ["Artist Four"], 200000, "TEST004")
        ]
        
        self.source_provider.list_tracks.return_value = all_tracks
        
        # Mock target provider responses for remaining tracks
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
        
        self.target_provider.add_tracks_batch.return_value = AddResult(
            added=2,
            duplicates=0,
            errors=0
        )
        
        # Mock matcher
        self.matcher.find_best_match.side_effect = [
            MatchResult(uri="spotify:track:3", confidence=1.0, reason="isrc_exact"),
            MatchResult(uri="spotify:track:4", confidence=1.0, reason="isrc_exact")
        ]
        
        # Execute transfer
        result = self.pipeline.transfer_playlist(
            source_playlist=source_playlist,
            job_id="test_job_1"
        )
        
        # Verify checkpoint was loaded
        self.checkpoint_manager.load_checkpoint.assert_called_once_with("test_job_1", "source_playlist_1")
        
        # Verify only remaining tracks were processed
        assert self.target_provider.add_tracks_batch.call_count == 1
        self.target_provider.add_tracks_batch.assert_called_with(
            "target_playlist_1",
            ["spotify:track:3", "spotify:track:4"]
        )

    def test_transfer_playlist_handles_not_found_tracks(self):
        """Test playlist transfer handles tracks that can't be found."""
        source_playlist = Playlist(
            id="source_playlist_1",
            name="Mixed Playlist",
            owner_id="user_1",
            is_owned=True
        )
        
        source_tracks = [
            Track("track_1", "Found Song", ["Found Artist"], 180000, "FOUND001"),
            Track("track_2", "Not Found Song", ["Unknown Artist"], 200000, None)
        ]
        
        self.source_provider.list_tracks.return_value = source_tracks
        
        # Mock target provider responses
        self.target_provider.find_track_candidates.side_effect = [
            [Candidate(uri="spotify:track:1", confidence=1.0, reason="isrc_exact")],
            []  # No candidates for second track
        ]
        
        self.target_provider.resolve_or_create_playlist.return_value = Playlist(
            id="target_playlist_1",
            name="Mixed Playlist",
            owner_id="target_user",
            is_owned=True
        )
        
        self.target_provider.add_tracks_batch.return_value = AddResult(
            added=1,
            duplicates=0,
            errors=0
        )
        
        # Mock matcher
        self.matcher.find_best_match.side_effect = [
            MatchResult(uri="spotify:track:1", confidence=1.0, reason="isrc_exact"),
            MatchResult(uri=None, confidence=0.0, reason="not_found")
        ]
        
        # Mock checkpoint manager
        self.checkpoint_manager.load_checkpoint.return_value = None
        
        # Execute transfer
        result = self.pipeline.transfer_playlist(
            source_playlist=source_playlist,
            job_id="test_job_1"
        )
        
        # Verify results
        assert result.total_tracks == 2
        assert result.matched_tracks == 1
        assert result.not_found_tracks == 1
        assert result.added_tracks == 1
        
        # Verify only found track was added
        self.target_provider.add_tracks_batch.assert_called_once_with(
            "target_playlist_1",
            ["spotify:track:1"]
        )


class TestBatchProcessor:
    """Tests for batch processing functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.target_provider = Mock()
        self.checkpoint_manager = Mock()
        self.processor = BatchProcessor(
            target_provider=self.target_provider,
            checkpoint_manager=self.checkpoint_manager,
            batch_size=3,
            max_retries=3
        )

    def test_process_batch_success(self):
        """Test successful batch processing."""
        track_uris = ["spotify:track:1", "spotify:track:2", "spotify:track:3"]
        
        self.target_provider.add_tracks_batch.return_value = AddResult(
            added=3,
            duplicates=0,
            errors=0
        )
        
        result = self.processor.process_batch(
            playlist_id="target_playlist_1",
            track_uris=track_uris,
            job_id="test_job",
            batch_index=0
        )
        
        assert result.added == 3
        assert result.duplicates == 0
        assert result.errors == 0
        
        self.target_provider.add_tracks_batch.assert_called_once_with(
            "target_playlist_1",
            track_uris
        )

    def test_process_batch_with_rate_limiting(self):
        """Test batch processing with rate limiting and retry."""
        track_uris = ["spotify:track:1", "spotify:track:2"]
        
        # First call raises rate limit, second succeeds
        self.target_provider.add_tracks_batch.side_effect = [
            RateLimited(retry_after_ms=1000),
            AddResult(added=2, duplicates=0, errors=0)
        ]
        
        with patch('time.sleep') as mock_sleep:
            result = self.processor.process_batch(
                playlist_id="target_playlist_1",
                track_uris=track_uris,
                job_id="test_job",
                batch_index=0
            )
        
        # Should have slept for rate limit
        mock_sleep.assert_called_once_with(1.0)  # 1000ms = 1s
        
        # Should have succeeded on retry
        assert result.added == 2
        assert self.target_provider.add_tracks_batch.call_count == 2

    def test_process_batch_with_exponential_backoff(self):
        """Test batch processing with exponential backoff on temporary failures."""
        track_uris = ["spotify:track:1"]
        
        # Fail twice, then succeed
        self.target_provider.add_tracks_batch.side_effect = [
            TemporaryFailure("Server error"),
            TemporaryFailure("Server error"),
            AddResult(added=1, duplicates=0, errors=0)
        ]
        
        with patch('time.sleep') as mock_sleep:
            result = self.processor.process_batch(
                playlist_id="target_playlist_1",
                track_uris=track_uris,
                job_id="test_job",
                batch_index=0
            )
        
        # Should have used exponential backoff: 1s, 2s
        expected_sleep_calls = [call(1), call(2)]
        mock_sleep.assert_has_calls(expected_sleep_calls)
        
        # Should have succeeded on third attempt
        assert result.added == 1
        assert self.target_provider.add_tracks_batch.call_count == 3

    def test_process_batch_max_retries_exceeded(self):
        """Test batch processing when max retries are exceeded."""
        track_uris = ["spotify:track:1"]
        
        # Always fail
        self.target_provider.add_tracks_batch.side_effect = TemporaryFailure("Server error")
        
        with patch('time.sleep'):
            with pytest.raises(TemporaryFailure):
                self.processor.process_batch(
                    playlist_id="target_playlist_1",
                    track_uris=track_uris,
                    job_id="test_job",
                    batch_index=0
                )
        
        # Should have tried max_retries + 1 times (3 retries + initial attempt = 4)
        assert self.target_provider.add_tracks_batch.call_count == 4

    def test_split_into_batches(self):
        """Test splitting URIs into batches."""
        track_uris = [f"spotify:track:{i}" for i in range(1, 8)]  # 7 tracks
        
        processor = BatchProcessor(
            target_provider=self.target_provider,
            checkpoint_manager=self.checkpoint_manager,
            batch_size=3,
            max_retries=3
        )
        
        batches = processor.split_into_batches(track_uris)
        
        expected_batches = [
            ["spotify:track:1", "spotify:track:2", "spotify:track:3"],
            ["spotify:track:4", "spotify:track:5", "spotify:track:6"],
            ["spotify:track:7"]
        ]
        
        assert batches == expected_batches


class TestCheckpointManager:
    """Tests for checkpoint management functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = CheckpointManager(checkpoint_dir=self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_save_and_load_checkpoint(self):
        """Test saving and loading checkpoints."""
        checkpoint_data = {
            "jobId": "test_job_1",
            "playlistId": "playlist_1",
            "batchIndex": 2,
            "stage": "writing",
            "cursor": {
                "trackIndex": 5,
                "batchTrackIndex": 1
            },
            "addedUris": ["spotify:track:1", "spotify:track:2"],
            "attempts": 1,
            "updatedAt": datetime.now().isoformat()
        }
        
        # Save checkpoint
        self.manager.save_checkpoint("test_job_1", "playlist_1", checkpoint_data)
        
        # Load checkpoint
        loaded = self.manager.load_checkpoint("test_job_1", "playlist_1")
        
        assert loaded == checkpoint_data

    def test_load_nonexistent_checkpoint(self):
        """Test loading a checkpoint that doesn't exist."""
        result = self.manager.load_checkpoint("nonexistent_job", "nonexistent_playlist")
        assert result is None

    def test_delete_checkpoint(self):
        """Test deleting a checkpoint."""
        checkpoint_data = {
            "jobId": "test_job_1",
            "playlistId": "playlist_1",
            "batchIndex": 0,
            "stage": "completed",
            "updatedAt": datetime.now().isoformat()
        }
        
        # Save checkpoint
        self.manager.save_checkpoint("test_job_1", "playlist_1", checkpoint_data)
        
        # Verify it exists
        loaded = self.manager.load_checkpoint("test_job_1", "playlist_1")
        assert loaded is not None
        
        # Delete checkpoint
        self.manager.delete_checkpoint("test_job_1", "playlist_1")
        
        # Verify it's gone
        loaded = self.manager.load_checkpoint("test_job_1", "playlist_1")
        assert loaded is None

    def test_checkpoint_file_naming(self):
        """Test checkpoint file naming convention."""
        job_id = "test_job_1"
        playlist_id = "playlist_123"
        
        expected_filename = f"{job_id}_{playlist_id}.json"
        expected_path = os.path.join(self.temp_dir, expected_filename)
        
        checkpoint_data = {
            "jobId": job_id,
            "playlistId": playlist_id,
            "stage": "scanning",
            "updatedAt": datetime.now().isoformat()
        }
        
        self.manager.save_checkpoint(job_id, playlist_id, checkpoint_data)
        
        # Verify file was created with correct name
        assert os.path.exists(expected_path)
        
        # Verify content
        with open(expected_path, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data == checkpoint_data

    def test_list_checkpoints_for_job(self):
        """Test listing all checkpoints for a job."""
        job_id = "test_job_1"
        
        # Create multiple checkpoints for the same job
        playlists = ["playlist_1", "playlist_2", "playlist_3"]
        for playlist_id in playlists:
            checkpoint_data = {
                "jobId": job_id,
                "playlistId": playlist_id,
                "stage": "writing",
                "updatedAt": datetime.now().isoformat()
            }
            self.manager.save_checkpoint(job_id, playlist_id, checkpoint_data)
        
        # Create checkpoint for different job
        self.manager.save_checkpoint("other_job", "other_playlist", {
            "jobId": "other_job",
            "playlistId": "other_playlist",
            "stage": "completed",
            "updatedAt": datetime.now().isoformat()
        })
        
        # List checkpoints for test_job_1
        checkpoints = self.manager.list_checkpoints_for_job(job_id)
        
        # Should only return checkpoints for test_job_1
        assert len(checkpoints) == 3
        for checkpoint in checkpoints:
            assert checkpoint["jobId"] == job_id
            assert checkpoint["playlistId"] in playlists
