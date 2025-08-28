from datetime import datetime
from typing import Dict, Any

import pytest

from app.domain.entities import Track, Playlist, Candidate


def test_report_header_creation():
    from app.crosscutting.reporting import ReportHeader, create_report_header

    job_id = "job-123"
    source = "yandex"
    target = "spotify"
    snapshot_hash = "abc123"
    dry_run = False

    header = create_report_header(job_id, source, target, snapshot_hash, dry_run)

    assert header.job_id == job_id
    assert header.source == source
    assert header.target == target
    assert header.snapshot_hash == snapshot_hash
    assert header.dry_run == dry_run
    assert header.started_at is not None
    assert header.finished_at is None


def test_playlist_summary_creation():
    from app.crosscutting.reporting import PlaylistSummary, create_playlist_summary

    playlist_id = "playlist-456"
    name = "My Favorites"
    totals = {"tracks": 10, "matched": 8, "added": 7, "duplicates": 1, "errors": 0}

    summary = create_playlist_summary(playlist_id, name, totals)

    assert summary.playlist_id == playlist_id
    assert summary.name == name
    assert summary.totals == totals


def test_track_result_creation():
    from app.crosscutting.reporting import TrackResult, TrackStatus, create_track_result

    source_track_id = "track-789"
    status = TrackStatus.MATCHED
    confidence = 0.95
    reason = "exact_match"
    candidates = [
        Candidate(uri="spotify:track:abc", confidence=0.95, reason="exact"),
        Candidate(uri="spotify:track:def", confidence=0.85, reason="fuzzy"),
    ]

    result = create_track_result(
        source_track_id, status, confidence, reason, candidates
    )

    assert result.source_track_id == source_track_id
    assert result.status == status
    assert result.confidence == confidence
    assert result.reason == reason
    assert result.candidates == candidates


def test_report_creation_and_serialization():
    from app.crosscutting.reporting import (
        Report,
        create_report,
        create_report_header,
        create_playlist_summary,
        create_track_result,
        TrackStatus,
    )

    # Create header
    header = create_report_header("job-123", "yandex", "spotify", "hash123", False)
    header.finished_at = datetime.utcnow()

    # Create playlist summary
    summary = create_playlist_summary(
        "playlist-456", "My Favorites", {"tracks": 2, "matched": 2, "added": 2, "duplicates": 0, "errors": 0}
    )

    # Create track results
    track_results = [
        create_track_result(
            "track-1",
            TrackStatus.MATCHED,
            0.95,
            "exact_match",
            [Candidate(uri="spotify:track:abc", confidence=0.95, reason="exact")],
        ),
        create_track_result(
            "track-2",
            TrackStatus.NOT_FOUND,
            0.0,
            "no_candidates",
            [],
        ),
    ]

    # Create report
    report = create_report(header, [summary], track_results)

    # Test serialization
    json_data = report.to_json()
    assert "header" in json_data
    assert "playlists" in json_data
    assert "tracks" in json_data

    # Test deserialization
    restored = Report.from_json(json_data)
    assert restored.header.job_id == report.header.job_id
    assert len(restored.playlists) == len(report.playlists)
    assert len(restored.tracks) == len(report.tracks)


def test_metrics_collection():
    from app.crosscutting.reporting import MetricsCollector

    collector = MetricsCollector()

    # Record metrics
    collector.record_match_rate(0.85)
    collector.record_write_success_rate(0.95)
    collector.record_retry_count(3)
    collector.record_rl_wait_ms(1500)
    collector.record_duration_ms(30000)

    # Get metrics
    metrics = collector.get_metrics()

    assert "match_rate" in metrics
    assert "write_success_rate" in metrics
    assert "retry_count" in metrics
    assert "rl_wait_ms" in metrics
    assert "duration_ms" in metrics

    assert metrics["match_rate"] == 0.85
    assert metrics["write_success_rate"] == 0.95
    assert metrics["retry_count"] == 3
    assert metrics["rl_wait_ms"] == 1500
    assert metrics["duration_ms"] == 30000


def test_metrics_aggregation():
    from app.crosscutting.reporting import MetricsCollector

    collector = MetricsCollector()

    # Record multiple values for aggregation
    collector.record_retry_count(1)
    collector.record_retry_count(2)
    collector.record_retry_count(3)

    collector.record_rl_wait_ms(1000)
    collector.record_rl_wait_ms(2000)

    metrics = collector.get_metrics()

    # Should aggregate retry_count (sum) and rl_wait_ms (sum)
    assert metrics["retry_count"] == 6
    assert metrics["rl_wait_ms"] == 3000


def test_report_schema_validation():
    from app.crosscutting.reporting import (
        Report,
        create_report,
        create_report_header,
        create_playlist_summary,
        create_track_result,
        TrackStatus,
    )

    # Create minimal valid report
    header = create_report_header("job-123", "yandex", "spotify", "hash123", False)
    header.finished_at = datetime.utcnow()

    summary = create_playlist_summary(
        "playlist-456", "Test", {"tracks": 1, "matched": 1, "added": 1, "duplicates": 0, "errors": 0}
    )

    track_result = create_track_result(
        "track-1", TrackStatus.MATCHED, 0.95, "exact", []
    )

    report = create_report(header, [summary], [track_result])

    # Should not raise validation errors
    json_data = report.to_json()
    restored = Report.from_json(json_data)

    assert restored is not None


def test_empty_report_handling():
    from app.crosscutting.reporting import (
        create_report,
        create_report_header,
    )

    header = create_report_header("job-123", "yandex", "spotify", "hash123", False)
    header.finished_at = datetime.utcnow()

    # Create report with no playlists and no tracks
    report = create_report(header, [], [])

    json_data = report.to_json()
    assert "playlists" in json_data
    assert "tracks" in json_data
    assert json_data["playlists"] == []
    assert json_data["tracks"] == []


def test_track_status_enum():
    from app.crosscutting.reporting import TrackStatus

    # Test all status values
    assert TrackStatus.MATCHED == "matched"
    assert TrackStatus.ADDED == "added"
    assert TrackStatus.SKIPPED_DUPLICATE == "skipped_duplicate"
    assert TrackStatus.NOT_FOUND == "not_found"
    assert TrackStatus.AMBIGUOUS == "ambiguous"
    assert TrackStatus.ERROR == "error"
    assert TrackStatus.RL_DEFERRED == "rl_deferred"
    assert TrackStatus.SKIPPED_DRY_RUN == "skipped_dry_run"


def test_metrics_serialization():
    from app.crosscutting.reporting import MetricsCollector

    collector = MetricsCollector()
    collector.record_match_rate(0.85)
    collector.record_write_success_rate(0.95)

    metrics = collector.get_metrics()
    
    # Test JSON serialization
    json_data = collector.to_json()
    assert "match_rate" in json_data
    assert "write_success_rate" in json_data
    assert json_data["match_rate"] == 0.85
    assert json_data["write_success_rate"] == 0.95
