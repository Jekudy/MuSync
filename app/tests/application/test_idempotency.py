import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from app.application.idempotency import (
    calculate_snapshot_hash, build_track_key, create_checkpoint, recover_from_checkpoint,
    Checkpoint, CheckpointStorage
)


def test_snapshot_hash_is_stable_for_same_tracks_different_order():
    # Use Track objects instead of Mock to ensure proper normalization
    from app.domain.entities import Track
    
    tracks1 = [
        Track(source_id="1", title="Song A", artists=["Artist A"], duration_ms=2000),
        Track(source_id="2", title="Song B", artists=["Artist B"], duration_ms=2200),
    ]
    tracks2 = [
        Track(source_id="2", title="Song B", artists=["Artist B"], duration_ms=2200),
        Track(source_id="1", title="Song A", artists=["Artist A"], duration_ms=2000),
    ]
    
    hash1 = calculate_snapshot_hash(tracks1)
    hash2 = calculate_snapshot_hash(tracks2)
    
    assert hash1 == hash2


def test_snapshot_hash_different_for_different_tracks():
    tracks1 = [
        Mock(source_id="1", title="Song A", artists=["Artist A"], duration_ms=2000),
    ]
    tracks2 = [
        Mock(source_id="1", title="Song A", artists=["Artist A"], duration_ms=2000),
        Mock(source_id="2", title="Song B", artists=["Artist B"], duration_ms=2200),
    ]
    
    hash1 = calculate_snapshot_hash(tracks1)
    hash2 = calculate_snapshot_hash(tracks2)
    
    assert hash1 != hash2


def test_track_key_prefers_isrc_when_present():
    from app.domain.entities import Track
    
    track_with_isrc = Track(
        source_id="1", title="Song A", artists=["Artist A"], duration_ms=2000,
        isrc="USRC12345678"
    )
    track_without_isrc = Track(
        source_id="1", title="Song A", artists=["Artist A"], duration_ms=2000,
        isrc=None
    )
    
    key1 = build_track_key(track_with_isrc)
    key2 = build_track_key(track_without_isrc)
    
    assert "USRC12345678" in key1
    assert "song a" in key2  # Normalized to lowercase
    assert key1 != key2


def test_track_key_duration_tolerance():
    track1 = Mock(
        source_id="1", title="Song A", artists=["Artist A"], duration_ms=2000,
        isrc=None
    )
    track2 = Mock(
        source_id="1", title="Song A", artists=["Artist A"], duration_ms=2001,
        isrc=None
    )
    
    key1 = build_track_key(track1)
    key2 = build_track_key(track2)
    
    # Should be the same due to duration tolerance
    assert key1 == key2


def test_checkpoint_creation_and_recovery():
    checkpoint = create_checkpoint("job123", "playlist456", 1, ["spotify:track:abc", "spotify:track:def"])
    
    assert checkpoint.job_id == "job123"
    assert checkpoint.playlist_id == "playlist456"
    assert checkpoint.batch_index == 1
    assert checkpoint.added_uris == ["spotify:track:abc", "spotify:track:def"]
    assert checkpoint.updated_at is not None


def test_checkpoint_storage_and_loading():
    checkpoint = create_checkpoint("job123", "playlist456", 1, ["spotify:track:abc"])
    
    # Test recovery
    recovered_uris = recover_from_checkpoint(checkpoint)
    
    assert recovered_uris == ["spotify:track:abc"]


def test_empty_snapshot_hash():
    """Test creating snapshot hash for empty track list."""
    empty_tracks = []
    hash_value = calculate_snapshot_hash(empty_tracks)
    
    assert hash_value is not None
    assert isinstance(hash_value, str)
    assert len(hash_value) > 0


def test_checkpoint_serialization():
    """Test checkpoint serialization and deserialization."""
    checkpoint = create_checkpoint("job123", "playlist456", 1, ["spotify:track:abc"])
    
    # Test serialization
    json_data = checkpoint.to_json()
    assert "job_id" in json_data
    assert "playlist_id" in json_data
    assert "batch_index" in json_data
    assert "added_uris" in json_data
    assert "updated_at" in json_data
    
    # Test deserialization
    restored = Checkpoint.from_json(json_data)
    assert restored.job_id == checkpoint.job_id
    assert restored.playlist_id == checkpoint.playlist_id
    assert restored.batch_index == checkpoint.batch_index
    assert restored.added_uris == checkpoint.added_uris


def test_track_key_with_none_values():
    """Test track key building with None values."""
    track = Mock(
        source_id="1", title="Song A", artists=["Artist A"], duration_ms=2000,
        isrc=None
    )
    
    key = build_track_key(track)
    
    assert key is not None
    assert isinstance(key, str)
    assert len(key) > 0


def test_snapshot_hash_with_unicode_tracks():
    """Test snapshot hash creation with unicode track data."""
    tracks = [
        Mock(source_id="1", title="Песня А", artists=["Артист А"], duration_ms=2000),
        Mock(source_id="2", title="Song B", artists=["Artist B"], duration_ms=2200),
    ]
    
    hash_value = calculate_snapshot_hash(tracks)
    
    assert hash_value is not None
    assert isinstance(hash_value, str)
    assert len(hash_value) > 0


def test_checkpoint_storage_save_and_load():
    """Test CheckpointStorage save and load functionality."""
    storage = CheckpointStorage()
    checkpoint = create_checkpoint("job123", "playlist456", 1, ["spotify:track:abc"])
    
    # Test save
    storage.save_checkpoint(checkpoint)
    
    # Test load
    loaded = storage.load_checkpoints("job123", "playlist456")
    
    assert len(loaded) == 1
    assert loaded[0].job_id == checkpoint.job_id
    assert loaded[0].playlist_id == checkpoint.playlist_id
    assert loaded[0].batch_index == checkpoint.batch_index


def test_checkpoint_storage_load_nonexistent():
    """Test loading non-existent checkpoint."""
    storage = CheckpointStorage()
    
    loaded = storage.load_checkpoints("nonexistent", "nonexistent")
    
    assert len(loaded) == 0


def test_checkpoint_storage_multiple_batches():
    """Test storing multiple batches for same job/playlist."""
    storage = CheckpointStorage()
    
    checkpoint1 = create_checkpoint("job123", "playlist456", 1, ["spotify:track:abc"])
    checkpoint2 = create_checkpoint("job123", "playlist456", 2, ["spotify:track:def"])
    
    storage.save_checkpoint(checkpoint1)
    storage.save_checkpoint(checkpoint2)
    
    loaded = storage.load_checkpoints("job123", "playlist456")
    
    assert len(loaded) == 2
    assert loaded[0].batch_index == 1
    assert loaded[1].batch_index == 2
