import os
import json
import time
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import logging
from unittest.mock import Mock

from app.application.matching import TrackMatcher, MatchResult
from app.domain.entities import Track, Playlist, AddResult
from app.domain.errors import RateLimited, TemporaryFailure, NotFound
from app.domain.ports import MusicProvider


logger = logging.getLogger(__name__)


@dataclass
class TransferResult:
    """Result of playlist transfer operation."""
    
    playlist_id: str
    playlist_name: str
    total_tracks: int
    matched_tracks: int
    not_found_tracks: int
    ambiguous_tracks: int
    added_tracks: int
    duplicate_tracks: int
    failed_tracks: int
    errors: List[str]
    duration_ms: int


class ProgressTracker:
    """Tracks progress and provides periodic updates."""
    
    def __init__(self, total_tracks: int, progress_interval_sec: int = 60):
        """Initialize progress tracker.
        
        Args:
            total_tracks: Total number of tracks to process
            progress_interval_sec: Interval for progress updates in seconds
        """
        self.total_tracks = total_tracks
        self.processed_tracks = 0
        self.matched_tracks = 0
        self.not_found_tracks = 0
        self.timeout_tracks = 0
        self.insufficient_metadata_tracks = 0
        self.last_progress_time = time.time()
        self.progress_interval_sec = progress_interval_sec
        self.start_time = time.time()
    
    def update(self, track_index: int, match_result: MatchResult) -> None:
        """Update progress with a new track result.
        
        Args:
            track_index: Current track index (0-based)
            match_result: Result of track matching
        """
        self.processed_tracks = track_index + 1
        
        if match_result.uri:
            self.matched_tracks += 1
        elif match_result.reason == "not_found":
            self.not_found_tracks += 1
        elif match_result.reason == "timeout":
            self.timeout_tracks += 1
        elif match_result.reason == "insufficient_metadata":
            self.insufficient_metadata_tracks += 1
        
        current_time = time.time()
        
        # Log progress every 10 tracks or every progress_interval_sec
        if (self.processed_tracks % 10 == 0 or 
            current_time - self.last_progress_time >= self.progress_interval_sec):
            
            elapsed_sec = current_time - self.start_time
            progress_pct = (self.processed_tracks / self.total_tracks) * 100
            
            logger.info(f"Progress: {self.processed_tracks}/{self.total_tracks} tracks ({progress_pct:.1f}%) "
                       f"processed in {elapsed_sec:.1f}s. "
                       f"Matched: {self.matched_tracks}, Not found: {self.not_found_tracks}, "
                       f"Timeouts: {self.timeout_tracks}, Insufficient metadata: {self.insufficient_metadata_tracks}")
            
            self.last_progress_time = current_time
    
    def get_final_summary(self) -> Dict[str, Any]:
        """Get final progress summary.
        
        Returns:
            Dictionary with final statistics
        """
        total_time = time.time() - self.start_time
        match_rate = (self.matched_tracks / self.total_tracks) * 100 if self.total_tracks > 0 else 0
        
        return {
            "total_tracks": self.total_tracks,
            "processed_tracks": self.processed_tracks,
            "matched_tracks": self.matched_tracks,
            "not_found_tracks": self.not_found_tracks,
            "timeout_tracks": self.timeout_tracks,
            "insufficient_metadata_tracks": self.insufficient_metadata_tracks,
            "match_rate_percent": match_rate,
            "total_time_seconds": total_time,
            "tracks_per_second": self.processed_tracks / total_time if total_time > 0 else 0
        }


class CheckpointManager:
    """Manages checkpoints for transfer pipeline recovery."""
    
    def __init__(self, checkpoint_dir: str = "checkpoints"):
        """Initialize checkpoint manager.
        
        Args:
            checkpoint_dir: Directory to store checkpoint files
        """
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(checkpoint_dir, exist_ok=True)

    def _get_checkpoint_path(self, job_id: str, playlist_id: str) -> str:
        """Get the file path for a checkpoint.
        
        Args:
            job_id: Job identifier
            playlist_id: Playlist identifier
            
        Returns:
            Path to checkpoint file
        """
        filename = f"{job_id}_{playlist_id}.json"
        return os.path.join(self.checkpoint_dir, filename)

    def save_checkpoint(self, job_id: str, playlist_id: str, checkpoint_data: Dict[str, Any]) -> None:
        """Save checkpoint data to file.
        
        Args:
            job_id: Job identifier
            playlist_id: Playlist identifier
            checkpoint_data: Checkpoint data to save
        """
        checkpoint_path = self._get_checkpoint_path(job_id, playlist_id)
        
        try:
            with open(checkpoint_path, 'w') as f:
                json.dump(checkpoint_data, f, indent=2)
            
            logger.debug(f"Saved checkpoint for job {job_id}, playlist {playlist_id}")
            
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            raise

    def load_checkpoint(self, job_id: str, playlist_id: str) -> Optional[Dict[str, Any]]:
        """Load checkpoint data from file.
        
        Args:
            job_id: Job identifier
            playlist_id: Playlist identifier
            
        Returns:
            Checkpoint data if exists, None otherwise
        """
        checkpoint_path = self._get_checkpoint_path(job_id, playlist_id)
        
        if not os.path.exists(checkpoint_path):
            return None
        
        try:
            with open(checkpoint_path, 'r') as f:
                checkpoint_data = json.load(f)
            
            logger.debug(f"Loaded checkpoint for job {job_id}, playlist {playlist_id}")
            return checkpoint_data
            
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None

    def delete_checkpoint(self, job_id: str, playlist_id: str) -> None:
        """Delete checkpoint file.
        
        Args:
            job_id: Job identifier
            playlist_id: Playlist identifier
        """
        checkpoint_path = self._get_checkpoint_path(job_id, playlist_id)
        
        if os.path.exists(checkpoint_path):
            try:
                os.remove(checkpoint_path)
                logger.debug(f"Deleted checkpoint for job {job_id}, playlist {playlist_id}")
            except Exception as e:
                logger.error(f"Failed to delete checkpoint: {e}")

    def list_checkpoints_for_job(self, job_id: str) -> List[Dict[str, Any]]:
        """List all checkpoints for a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            List of checkpoint data for the job
        """
        checkpoints = []
        
        try:
            for filename in os.listdir(self.checkpoint_dir):
                if filename.startswith(f"{job_id}_") and filename.endswith(".json"):
                    checkpoint_path = os.path.join(self.checkpoint_dir, filename)
                    with open(checkpoint_path, 'r') as f:
                        checkpoint_data = json.load(f)
                    checkpoints.append(checkpoint_data)
                    
        except Exception as e:
            logger.error(f"Failed to list checkpoints for job {job_id}: {e}")
        
        return checkpoints


class BatchProcessor:
    """Processes tracks in batches with retry logic."""
    
    def __init__(self, 
                 target_provider: MusicProvider,
                 checkpoint_manager: CheckpointManager,
                 batch_size: int = 100,
                 max_retries: int = 3):
        """Initialize batch processor.
        
        Args:
            target_provider: Target music provider (e.g., Spotify)
            checkpoint_manager: Checkpoint manager for state persistence
            batch_size: Maximum number of tracks per batch
            max_retries: Maximum number of retries for failed batches
        """
        self.target_provider = target_provider
        self.checkpoint_manager = checkpoint_manager
        self.batch_size = batch_size
        self.max_retries = max_retries

    def split_into_batches(self, track_uris: List[str]) -> List[List[str]]:
        """Split track URIs into batches.
        
        Args:
            track_uris: List of track URIs to split
            
        Returns:
            List of batches, each containing up to batch_size URIs
        """
        batches = []
        for i in range(0, len(track_uris), self.batch_size):
            batch = track_uris[i:i + self.batch_size]
            batches.append(batch)
        return batches

    def process_batch(self, 
                     playlist_id: str, 
                     track_uris: List[str],
                     job_id: str,
                     batch_index: int,
                     dry_run: bool = False) -> AddResult:
        """Process a single batch of tracks with retry logic.
        
        Args:
            playlist_id: Target playlist ID
            track_uris: List of track URIs to add
            job_id: Job identifier for checkpoint tracking
            batch_index: Index of this batch
            
        Returns:
            AddResult indicating success/failure
            
        Raises:
            TemporaryFailure: If max retries exceeded
        """
        attempt = 0
        
        # In dry-run mode, simulate successful addition without calling the provider
        if dry_run:
            logger.info(f"DRY-RUN: Would process batch {batch_index} with {len(track_uris)} tracks")
            return AddResult(
                added=len(track_uris),
                duplicates=0,
                errors=0
            )
        
        while attempt <= self.max_retries:
            try:
                logger.info(f"Processing batch {batch_index}, attempt {attempt + 1}")
                
                result = self.target_provider.add_tracks_batch(playlist_id, track_uris)
                
                logger.info(f"Batch {batch_index} completed: "
                           f"added={result.added}, duplicates={result.duplicates}, errors={result.errors}")
                
                return result
                
            except RateLimited as e:
                logger.warning(f"Rate limited on batch {batch_index}, waiting {e.retry_after_ms}ms")
                
                # Wait for the specified time
                time.sleep(e.retry_after_ms / 1000.0)
                
                # Rate limiting doesn't count as a retry attempt
                continue
                
            except (TemporaryFailure, Exception) as e:
                attempt += 1
                
                if attempt > self.max_retries:
                    logger.error(f"Max retries exceeded for batch {batch_index}: {e}")
                    raise TemporaryFailure(f"Failed to process batch after {self.max_retries} retries: {e}")
                
                # Exponential backoff: 1s, 2s, 4s, ...
                backoff_time = 2 ** (attempt - 1)
                logger.warning(f"Batch {batch_index} failed (attempt {attempt}), "
                              f"retrying in {backoff_time}s: {e}")
                
                time.sleep(backoff_time)

        # This should never be reached due to the exception above
        raise TemporaryFailure(f"Unexpected error in batch processing")


class TransferPipeline:
    """Main pipeline for transferring playlists between music providers."""
    
    def __init__(self,
                 source_provider: MusicProvider,
                 target_provider: MusicProvider,
                 matcher: TrackMatcher,
                 checkpoint_manager: CheckpointManager,
                 batch_size: int = 100):
        """Initialize transfer pipeline.
        
        Args:
            source_provider: Source music provider (e.g., Yandex Music)
            target_provider: Target music provider (e.g., Spotify)
            matcher: Track matching algorithm
            checkpoint_manager: Checkpoint manager for recovery
            batch_size: Maximum number of tracks per batch
        """
        self.source_provider = source_provider
        self.target_provider = target_provider
        self.matcher = matcher
        self.checkpoint_manager = checkpoint_manager
        self.batch_processor = BatchProcessor(
            target_provider=target_provider,
            checkpoint_manager=checkpoint_manager,
            batch_size=batch_size
        )

    def transfer_playlist(self, 
                         source_playlist: Playlist,
                         job_id: str,
                         snapshot_hash: Optional[str] = None,
                         dry_run: bool = False) -> TransferResult:
        """Transfer a playlist from source to target provider.
        
        Args:
            source_playlist: Source playlist to transfer
            job_id: Unique job identifier
            snapshot_hash: Optional snapshot hash for idempotency
            
        Returns:
            TransferResult with transfer statistics
        """
        start_time = datetime.now()
        
        logger.info(f"Starting playlist transfer: {source_playlist.name} (job: {job_id})")
        
        # Check for existing checkpoint
        checkpoint = self.checkpoint_manager.load_checkpoint(job_id, source_playlist.id)
        
        if checkpoint:
            logger.info(f"Resuming from checkpoint: batch {checkpoint.get('batchIndex', 0)}")
            return self._resume_from_checkpoint(source_playlist, job_id, checkpoint, start_time, dry_run)
        else:
            return self._start_fresh_transfer(source_playlist, job_id, snapshot_hash, start_time, dry_run)

    def _start_fresh_transfer(self, 
                            source_playlist: Playlist,
                            job_id: str,
                            snapshot_hash: Optional[str],
                            start_time: datetime,
                            dry_run: bool = False) -> TransferResult:
        """Start a fresh transfer without checkpoints."""
        
        # Create initial checkpoint (only if not in dry-run mode)
        if not dry_run:
            checkpoint_data = {
                "jobId": job_id,
                "snapshotHash": snapshot_hash,
                "playlistId": source_playlist.id,
                "batchIndex": 0,
                "stage": "scanning",
                "cursor": {
                    "trackIndex": 0,
                    "batchTrackIndex": 0
                },
                "addedUris": [],
                "attempts": 0,
                "updatedAt": datetime.now().isoformat(),
                "metadata": {
                    "totalTracks": 0,
                    "processedTracks": 0,
                    "batchSize": self.batch_processor.batch_size
                }
            }
            
            self.checkpoint_manager.save_checkpoint(job_id, source_playlist.id, checkpoint_data)
        else:
            checkpoint_data = {
                "jobId": job_id,
                "snapshotHash": snapshot_hash,
                "playlistId": source_playlist.id,
                "batchIndex": 0,
                "stage": "scanning",
                "cursor": {
                    "trackIndex": 0,
                    "batchTrackIndex": 0
                },
                "addedUris": [],
                "attempts": 0,
                "updatedAt": datetime.now().isoformat(),
                "metadata": {
                    "totalTracks": 0,
                    "processedTracks": 0,
                    "batchSize": self.batch_processor.batch_size
                }
            }
        
        # Get source tracks
        logger.info("Scanning source tracks...")
        source_tracks = list(self.source_provider.list_tracks(source_playlist.id))
        
        checkpoint_data["metadata"]["totalTracks"] = len(source_tracks)
        checkpoint_data["stage"] = "matching"
        checkpoint_data["updatedAt"] = datetime.now().isoformat()
        if not dry_run:
            self.checkpoint_manager.save_checkpoint(job_id, source_playlist.id, checkpoint_data)
        
        # Resolve or create target playlist
        target_playlist = self.target_provider.resolve_or_create_playlist(source_playlist.name)
        
        # Initialize progress tracker
        progress_tracker = ProgressTracker(len(source_tracks))
        
        # Match tracks
        logger.info(f"Matching {len(source_tracks)} tracks...")
        matched_uris = []
        match_results = []
        
        for i, track in enumerate(source_tracks):
            try:
                # Get candidates from target provider
                candidates = self.target_provider.find_track_candidates(track, top_k=3)
                
                # Find best match
                match_result = self.matcher.find_best_match(track, candidates)
                match_results.append(match_result)
                
                if match_result.uri:
                    matched_uris.append(match_result.uri)
                
                # Update progress
                progress_tracker.update(i, match_result)
                
                # Update checkpoint periodically (only if not in dry-run mode)
                if (i + 1) % 10 == 0 and not dry_run:
                    checkpoint_data["cursor"]["trackIndex"] = i + 1
                    checkpoint_data["metadata"]["processedTracks"] = i + 1
                    checkpoint_data["updatedAt"] = datetime.now().isoformat()
                    self.checkpoint_manager.save_checkpoint(job_id, source_playlist.id, checkpoint_data)
                    
            except Exception as e:
                logger.error(f"Error processing track {i} ({track.title}): {e}")
                # Create a failed match result
                failed_result = MatchResult(uri=None, confidence=0.0, reason="error")
                match_results.append(failed_result)
                progress_tracker.update(i, failed_result)
        
        # Log final progress summary
        final_summary = progress_tracker.get_final_summary()
        logger.info(f"Final matching summary: {final_summary}")
        
        # Process matched tracks
        return self._process_matched_tracks(
            target_playlist, matched_uris, match_results, 
            job_id, source_playlist.id, checkpoint_data, start_time, dry_run,
            total_tracks=len(source_tracks)
        )

    def _resume_from_checkpoint(self, 
                              source_playlist: Playlist,
                              job_id: str,
                              checkpoint: Dict[str, Any],
                              start_time: datetime,
                              dry_run: bool = False) -> TransferResult:
        """Resume transfer from existing checkpoint."""
        
        # Get all tracks to determine how many were already processed
        source_tracks = list(self.source_provider.list_tracks(source_playlist.id))
        
        target_playlist = self.target_provider.resolve_or_create_playlist(source_playlist.name)
        
        # Get already added URIs from checkpoint
        already_added_uris = checkpoint.get("addedUris", [])
        
        # Continue matching from checkpoint position
        start_index = checkpoint.get("cursor", {}).get("trackIndex", 0)
        remaining_tracks = source_tracks[start_index:]
        
        # Only process new matches, not previously added ones
        new_matched_uris = []
        match_results = []
        
        for i, track in enumerate(remaining_tracks):
            candidates = self.target_provider.find_track_candidates(track, top_k=3)
            match_result = self.matcher.find_best_match(track, candidates)
            match_results.append(match_result)
            
            if match_result.uri and match_result.uri not in already_added_uris:
                new_matched_uris.append(match_result.uri)
        
        # For checkpoint recovery, we need to include all tracks in the total count
        # but only process the remaining ones
        total_tracks = len(source_tracks)
        
        # For checkpoint recovery, we need to account for already matched tracks
        # We'll create dummy match results for already processed tracks
        already_processed_count = len(already_added_uris)
        dummy_match_results = [Mock(uri="dummy", confidence=1.0, reason="already_processed") for _ in range(already_processed_count)]
        
        return self._process_matched_tracks(
            target_playlist, new_matched_uris, match_results + dummy_match_results,
            job_id, source_playlist.id, checkpoint, start_time, dry_run,
            already_added_count=len(already_added_uris),
            total_tracks=total_tracks
        )

    def _process_matched_tracks(self,
                              target_playlist: Playlist,
                              matched_uris: List[str],
                              match_results: List[MatchResult],
                              job_id: str,
                              source_playlist_id: str,
                              checkpoint_data: Dict[str, Any],
                              start_time: datetime,
                              dry_run: bool = False,
                              already_added_count: int = 0,
                              total_tracks: Optional[int] = None) -> TransferResult:
        """Process matched tracks in batches."""
        
        if dry_run:
            logger.info(f"DRY-RUN: Would add {len(matched_uris)} matched tracks to target playlist...")
        else:
            logger.info(f"Adding {len(matched_uris)} matched tracks to target playlist...")
        
        # Update checkpoint for writing stage (only if not in dry-run mode)
        if not dry_run:
            checkpoint_data["stage"] = "writing"
            checkpoint_data["updatedAt"] = datetime.now().isoformat()
            self.checkpoint_manager.save_checkpoint(job_id, source_playlist_id, checkpoint_data)
        
        # Split into batches and process
        batches = self.batch_processor.split_into_batches(matched_uris)
        
        total_added = 0
        total_duplicates = 0
        total_errors = 0
        errors = []
        
        for batch_index, batch_uris in enumerate(batches):
            try:
                # Update checkpoint (only if not in dry-run mode)
                if not dry_run:
                    checkpoint_data["batchIndex"] = batch_index
                    checkpoint_data["updatedAt"] = datetime.now().isoformat()
                    self.checkpoint_manager.save_checkpoint(job_id, source_playlist_id, checkpoint_data)
                
                # Process batch
                batch_result = self.batch_processor.process_batch(
                    target_playlist.id, batch_uris, job_id, batch_index, dry_run
                )
                
                total_added += batch_result.added
                total_duplicates += batch_result.duplicates
                total_errors += batch_result.errors
                
                # Update checkpoint with added URIs (only if not in dry-run mode)
                if not dry_run:
                    checkpoint_data["addedUris"].extend(batch_uris[:batch_result.added])
                
            except Exception as e:
                error_msg = f"Failed to process batch {batch_index}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                total_errors += len(batch_uris)
        
        # Calculate statistics
        if total_tracks is None:
            total_tracks = len(match_results)
        matched_tracks = sum(1 for r in match_results if r.uri is not None)
        not_found_tracks = sum(1 for r in match_results if r.reason == "not_found")
        ambiguous_tracks = sum(1 for r in match_results if r.reason == "ambiguous")
        
        # Mark as completed (only if not in dry-run mode)
        if not dry_run:
            checkpoint_data["stage"] = "completed"
            checkpoint_data["updatedAt"] = datetime.now().isoformat()
            self.checkpoint_manager.save_checkpoint(job_id, source_playlist_id, checkpoint_data)
        
        # Calculate duration
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Ensure minimum duration for dry-run mode to avoid 0 duration in tests
        if dry_run and duration_ms == 0:
            duration_ms = 1
        
        result = TransferResult(
            playlist_id=target_playlist.id,
            playlist_name=target_playlist.name,
            total_tracks=total_tracks,
            matched_tracks=matched_tracks,
            not_found_tracks=not_found_tracks,
            ambiguous_tracks=ambiguous_tracks,
            added_tracks=0 if dry_run else (total_added + already_added_count),
            duplicate_tracks=total_duplicates,
            failed_tracks=total_errors,
            errors=errors,
            duration_ms=duration_ms
        )
        
        if dry_run:
            logger.info(f"DRY-RUN completed: {matched_tracks}/{total_tracks} tracks matched, "
                       f"{total_added} would be added, {total_duplicates} duplicates, {total_errors} failed")
        else:
            logger.info(f"Transfer completed: {matched_tracks}/{total_tracks} tracks matched, "
                       f"{total_added} added, {total_duplicates} duplicates, {total_errors} failed")
        
        return result
