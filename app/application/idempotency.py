import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any

from app.domain.entities import Track
from app.domain.normalization import build_track_key as domain_build_track_key


@dataclass
class Checkpoint:
    """Checkpoint for tracking batch progress and enabling idempotency."""
    
    job_id: str
    playlist_id: str
    batch_index: int
    added_uris: List[str]
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_json(self) -> Dict[str, Any]:
        """Serialize checkpoint to JSON."""
        return {
            "job_id": self.job_id,
            "playlist_id": self.playlist_id,
            "batch_index": self.batch_index,
            "added_uris": self.added_uris,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "Checkpoint":
        """Deserialize checkpoint from JSON."""
        return cls(
            job_id=data["job_id"],
            playlist_id=data["playlist_id"],
            batch_index=data["batch_index"],
            added_uris=data["added_uris"],
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


def build_track_key(track: Track, tolerance_ms: int = 2000) -> str:
    """Build a stable key for a track, preferring ISRC when available."""
    return domain_build_track_key(track, tolerance_ms)


def calculate_snapshot_hash(tracks: List[Track]) -> str:
    """Calculate a stable hash for a snapshot of tracks.
    
    The hash is deterministic and order-independent, allowing for
    idempotent operations across different runs with the same tracks.
    """
    if not tracks:
        # Empty snapshot gets a consistent hash
        return hashlib.sha256(b"empty_snapshot").hexdigest()
    
    # Build track keys and sort for stability
    track_keys = [build_track_key(track) for track in tracks]
    track_keys.sort()  # Ensure order independence
    
    # Create a stable string representation
    snapshot_str = "\n".join(track_keys)
    
    # Calculate SHA-256 hash
    return hashlib.sha256(snapshot_str.encode('utf-8')).hexdigest()


def create_checkpoint(
    job_id: str, 
    playlist_id: str, 
    batch_index: int, 
    added_uris: List[str]
) -> Checkpoint:
    """Create a new checkpoint for a batch operation."""
    return Checkpoint(
        job_id=job_id,
        playlist_id=playlist_id,
        batch_index=batch_index,
        added_uris=added_uris.copy(),  # Defensive copy
    )


def recover_from_checkpoint(checkpoint: Checkpoint) -> List[str]:
    """Recover the list of URIs that were successfully added in this batch."""
    return checkpoint.added_uris.copy()  # Defensive copy


class CheckpointStorage:
    """In-memory storage for checkpoints (MVP implementation).
    
    In production, this would be replaced with persistent storage
    (database, file system, etc.).
    """
    
    def __init__(self):
        self._checkpoints: Dict[str, List[Checkpoint]] = {}
    
    def _get_key(self, job_id: str, playlist_id: str) -> str:
        """Generate a storage key for job/playlist combination."""
        return f"{job_id}:{playlist_id}"
    
    def save_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Save a checkpoint, avoiding duplicates."""
        key = self._get_key(checkpoint.job_id, checkpoint.playlist_id)
        
        if key not in self._checkpoints:
            self._checkpoints[key] = []
        
        # Check for existing checkpoint with same batch_index
        existing = None
        for cp in self._checkpoints[key]:
            if cp.batch_index == checkpoint.batch_index:
                existing = cp
                break
        
        if existing:
            # Update existing checkpoint
            existing.added_uris = checkpoint.added_uris
            existing.updated_at = checkpoint.updated_at
        else:
            # Add new checkpoint
            self._checkpoints[key].append(checkpoint)
    
    def load_checkpoints(self, job_id: str, playlist_id: str) -> List[Checkpoint]:
        """Load all checkpoints for a job/playlist combination."""
        key = self._get_key(job_id, playlist_id)
        checkpoints = self._checkpoints.get(key, [])
        
        # Sort by batch_index for consistent ordering
        return sorted(checkpoints, key=lambda cp: cp.batch_index)
    
    def clear_checkpoints(self, job_id: str, playlist_id: str) -> None:
        """Clear all checkpoints for a job/playlist combination."""
        key = self._get_key(job_id, playlist_id)
        if key in self._checkpoints:
            del self._checkpoints[key]
