import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional

from app.domain.entities import Candidate


class TrackStatus(str, Enum):
    """Status of a track transfer operation."""
    
    MATCHED = "matched"
    ADDED = "added"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    ERROR = "error"
    RL_DEFERRED = "rl_deferred"
    SKIPPED_DRY_RUN = "skipped_dry_run"


@dataclass
class ReportHeader:
    """Header information for a transfer report."""
    
    job_id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    source: str = ""
    target: str = ""
    snapshot_hash: str = ""
    dry_run: bool = False

    def to_json(self) -> Dict[str, Any]:
        """Serialize header to JSON."""
        return {
            "jobId": self.job_id,
            "startedAt": self.started_at.isoformat(),
            "finishedAt": self.finished_at.isoformat() if self.finished_at else None,
            "source": self.source,
            "target": self.target,
            "snapshotHash": self.snapshot_hash,
            "dryRun": self.dry_run,
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "ReportHeader":
        """Deserialize header from JSON."""
        return cls(
            job_id=data["jobId"],
            started_at=datetime.fromisoformat(data["startedAt"]),
            finished_at=datetime.fromisoformat(data["finishedAt"]) if data.get("finishedAt") else None,
            source=data.get("source", ""),
            target=data.get("target", ""),
            snapshot_hash=data.get("snapshotHash", ""),
            dry_run=data.get("dryRun", False),
        )


@dataclass
class PlaylistSummary:
    """Summary statistics for a playlist transfer."""
    
    playlist_id: str
    name: str
    totals: Dict[str, int] = field(default_factory=dict)

    def to_json(self) -> Dict[str, Any]:
        """Serialize playlist summary to JSON."""
        return {
            "playlistId": self.playlist_id,
            "name": self.name,
            "totals": self.totals,
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "PlaylistSummary":
        """Deserialize playlist summary from JSON."""
        return cls(
            playlist_id=data["playlistId"],
            name=data["name"],
            totals=data.get("totals", {}),
        )


@dataclass
class TrackResult:
    """Result of a track transfer operation."""
    
    source_track_id: str
    status: TrackStatus
    confidence: float
    reason: Optional[str] = None
    candidates: List[Candidate] = field(default_factory=list)

    def to_json(self) -> Dict[str, Any]:
        """Serialize track result to JSON."""
        return {
            "sourceTrackId": self.source_track_id,
            "status": self.status.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "candidates": [
                {
                    "uri": c.uri,
                    "confidence": c.confidence,
                    "reason": c.reason,
                    # Optional metadata fields for diagnostics (present if provided)
                    "title": getattr(c, "title", None),
                    "artists": getattr(c, "artists", None),
                    "album": getattr(c, "album", None),
                    "duration_ms": getattr(c, "duration_ms", None),
                    "rank": getattr(c, "rank", None),
                    "album_type": getattr(c, "album_type", None),
                }
                for c in self.candidates
            ],
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "TrackResult":
        """Deserialize track result from JSON."""
        return cls(
            source_track_id=data["sourceTrackId"],
            status=TrackStatus(data["status"]),
            confidence=data["confidence"],
            reason=data.get("reason"),
            candidates=[
                Candidate(
                    uri=c["uri"],
                    confidence=c["confidence"],
                    reason=c["reason"],
                    title=c.get("title"),
                    artists=c.get("artists"),
                    album=c.get("album"),
                    duration_ms=c.get("duration_ms"),
                    rank=c.get("rank"),
                    album_type=c.get("album_type"),
                )
                for c in data.get("candidates", [])
            ],
        )


@dataclass
class Report:
    """Complete transfer report."""
    
    header: ReportHeader
    playlists: List[PlaylistSummary]
    tracks: List[TrackResult]

    def to_json(self) -> Dict[str, Any]:
        """Serialize report to JSON."""
        return {
            "header": self.header.to_json(),
            "playlists": [p.to_json() for p in self.playlists],
            "tracks": [t.to_json() for t in self.tracks],
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "Report":
        """Deserialize report from JSON."""
        return cls(
            header=ReportHeader.from_json(data["header"]),
            playlists=[PlaylistSummary.from_json(p) for p in data.get("playlists", [])],
            tracks=[TrackResult.from_json(t) for t in data.get("tracks", [])],
        )


class MetricsCollector:
    """Collects and aggregates metrics during transfer operations."""
    
    def __init__(self):
        self._metrics: Dict[str, Any] = {
            "match_rate": 0.0,
            "write_success_rate": 0.0,
            "retry_count": 0,
            "rl_wait_ms": 0,
            "duration_ms": 0,
        }
    
    def record_match_rate(self, rate: float) -> None:
        """Record match rate (0.0 to 1.0)."""
        self._metrics["match_rate"] = max(0.0, min(1.0, rate))
    
    def record_write_success_rate(self, rate: float) -> None:
        """Record write success rate (0.0 to 1.0)."""
        self._metrics["write_success_rate"] = max(0.0, min(1.0, rate))
    
    def record_retry_count(self, count: int) -> None:
        """Record retry count (additive)."""
        self._metrics["retry_count"] += max(0, count)
    
    def record_rl_wait_ms(self, wait_ms: int) -> None:
        """Record rate limit wait time in milliseconds (additive)."""
        self._metrics["rl_wait_ms"] += max(0, wait_ms)
    
    def record_duration_ms(self, duration_ms: int) -> None:
        """Record operation duration in milliseconds."""
        self._metrics["duration_ms"] = max(0, duration_ms)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        return self._metrics.copy()
    
    def to_json(self) -> Dict[str, Any]:
        """Serialize metrics to JSON."""
        return self.get_metrics()
    
    def reset(self) -> None:
        """Reset all metrics to initial values."""
        self._metrics = {
            "match_rate": 0.0,
            "write_success_rate": 0.0,
            "retry_count": 0,
            "rl_wait_ms": 0,
            "duration_ms": 0,
        }


# Factory functions for creating report components

def create_report_header(
    job_id: str,
    source: str,
    target: str,
    snapshot_hash: str,
    dry_run: bool = False,
) -> ReportHeader:
    """Create a new report header."""
    return ReportHeader(
        job_id=job_id,
        started_at=datetime.utcnow(),
        source=source,
        target=target,
        snapshot_hash=snapshot_hash,
        dry_run=dry_run,
    )


def create_playlist_summary(
    playlist_id: str,
    name: str,
    totals: Dict[str, int],
) -> PlaylistSummary:
    """Create a new playlist summary."""
    return PlaylistSummary(
        playlist_id=playlist_id,
        name=name,
        totals=totals.copy(),  # Defensive copy
    )


def create_track_result(
    source_track_id: str,
    status: TrackStatus,
    confidence: float,
    reason: Optional[str] = None,
    candidates: Optional[List[Candidate]] = None,
) -> TrackResult:
    """Create a new track result."""
    return TrackResult(
        source_track_id=source_track_id,
        status=status,
        confidence=max(0.0, min(1.0, confidence)),
        reason=reason,
        candidates=candidates or [],
    )


def create_report(
    header: ReportHeader,
    playlists: List[PlaylistSummary],
    tracks: List[TrackResult],
) -> Report:
    """Create a new report."""
    return Report(
        header=header,
        playlists=playlists.copy(),  # Defensive copy
        tracks=tracks.copy(),  # Defensive copy
    )
