from __future__ import annotations

from typing import Iterable, List, Protocol

from .entities import AddResult, Candidate, Playlist, Track


class MusicProvider(Protocol):
    """Port defining the minimal contract for music providers.

    Implementations must be pure with respect to the domain and should map provider-specific
    details into domain entities and results.
    """

    def list_owned_playlists(self) -> Iterable[Playlist]:
        """Return all playlists owned by the current user."""

    def list_tracks(self, playlist_id: str) -> Iterable[Track]:
        """Iterate tracks belonging to the given playlist."""

    def find_track_candidates(self, track: Track, top_k: int = 3) -> List[Candidate]:
        """Return up to top_k candidates for the given source track, sorted by confidence desc."""

    def resolve_or_create_playlist(self, name: str) -> Playlist:
        """Return an owned playlist by name, creating it if necessary."""

    def add_tracks_batch(self, playlist_id: str, track_uris: List[str]) -> AddResult:
        """Add up to provider's maximum batch size of tracks to the playlist."""


