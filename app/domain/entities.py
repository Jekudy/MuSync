from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Track:
    """Domain entity representing a music track independent of providers."""

    id: Optional[str] = None
    source_id: str = ""
    title: str = ""
    artists: List[str] = None
    duration_ms: int = 0
    isrc: Optional[str] = None
    album: Optional[str] = None
    uri: Optional[str] = None
    
    def __post_init__(self):
        if self.artists is None:
            object.__setattr__(self, 'artists', [])


@dataclass(frozen=True)
class Playlist:
    """Domain entity representing a playlist."""

    id: str
    name: str
    owner_id: str
    is_owned: bool = False
    track_count: int = 0


@dataclass(frozen=True)
class Candidate:
    """Search candidate returned by target providers like Spotify."""

    uri: str
    confidence: float
    reason: str
    # Optional metadata to support advanced selection and diagnostics
    title: Optional[str] = None
    artists: Optional[List[str]] = None
    album: Optional[str] = None
    duration_ms: Optional[int] = None
    rank: Optional[int] = None
    album_type: Optional[str] = None


@dataclass(frozen=True)
class AddResult:
    """Result of a batch add operation to a playlist."""

    added: int
    duplicates: int
    errors: int


