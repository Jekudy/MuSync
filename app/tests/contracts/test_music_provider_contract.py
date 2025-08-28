from typing import Iterable, List

from app.domain.entities import AddResult, Candidate, Playlist, Track
from app.domain.ports import MusicProvider


class FakeProvider(MusicProvider):
    def __init__(self) -> None:
        self._playlists = [
            Playlist(id="p1", name="My Fav", owner_id="u1", is_owned=True),
            Playlist(id="p2", name="Subscribed", owner_id="u2", is_owned=False),
        ]
        self._tracks = {
            "p1": [
                Track(source_id="t1", title="Song A", artists=["A"], duration_ms=2000),
                Track(source_id="t2", title="Song B", artists=["B"], duration_ms=2200),
            ]
        }
        self._store = []  # type: List[str]

    def list_owned_playlists(self) -> Iterable[Playlist]:
        return [p for p in self._playlists if p.is_owned]

    def list_tracks(self, playlist_id: str) -> Iterable[Track]:
        return list(self._tracks.get(playlist_id, []))

    def find_track_candidates(self, track: Track, top_k: int = 3) -> List[Candidate]:
        # Return deterministic candidates based on title
        base = track.title.lower().replace(" ", "-")
        return [
            Candidate(uri=f"spotify:track:{base}", confidence=0.95, reason="exact"),
        ][:top_k]

    def resolve_or_create_playlist(self, name: str) -> Playlist:
        for p in self._playlists:
            if p.name == name and p.is_owned:
                return p
        new = Playlist(id="p3", name=name, owner_id="u1", is_owned=True)
        self._playlists.append(new)
        return new

    def add_tracks_batch(self, playlist_id: str, track_uris: List[str]) -> AddResult:
        before = len(self._store)
        for uri in track_uris:
            if uri not in self._store:
                self._store.append(uri)
        added = len(self._store) - before
        duplicates = len(track_uris) - added
        return AddResult(added=added, duplicates=duplicates, errors=0)


def test_contract_iterables_and_semantics():
    provider = FakeProvider()

    owned = list(provider.list_owned_playlists())
    assert owned and all(p.is_owned for p in owned)

    tracks = list(provider.list_tracks(owned[0].id))
    assert isinstance(tracks, list)
    assert all(isinstance(t, Track) for t in tracks)

    cands = provider.find_track_candidates(tracks[0], top_k=2)
    assert cands and len(cands) <= 2
    assert cands[0].confidence >= 0.0 and cands[0].confidence <= 1.0

    playlist = provider.resolve_or_create_playlist("Exported")
    assert playlist.is_owned and playlist.name == "Exported"

    res = provider.add_tracks_batch(playlist.id, [c.uri for c in cands])
    assert res.added >= 0 and res.duplicates >= 0 and res.errors == 0

    # Idempotency at batch level (provider should not double-add within its storage simulation)
    res2 = provider.add_tracks_batch(playlist.id, [c.uri for c in cands])
    assert res2.duplicates >= 1


def test_contract_empty_playlists():
    """Test contract behavior with empty playlists."""
    provider = FakeProvider()
    
    # Test empty tracks for non-existent playlist
    tracks = list(provider.list_tracks("non-existent"))
    assert isinstance(tracks, list)
    assert len(tracks) == 0


def test_contract_candidate_confidence_bounds():
    """Test that candidate confidence is always between 0 and 1."""
    provider = FakeProvider()
    track = Track(source_id="t1", title="Test Song", artists=["Test Artist"], duration_ms=3000)
    
    candidates = provider.find_track_candidates(track, top_k=5)
    
    for candidate in candidates:
        assert 0.0 <= candidate.confidence <= 1.0, f"Confidence {candidate.confidence} out of bounds"


def test_contract_playlist_ownership():
    """Test that only owned playlists are returned by list_owned_playlists."""
    provider = FakeProvider()
    
    owned_playlists = list(provider.list_owned_playlists())
    
    # All returned playlists should be owned
    for playlist in owned_playlists:
        assert playlist.is_owned, f"Playlist {playlist.name} should be owned"
    
    # Should not return the subscribed playlist
    owned_names = [p.name for p in owned_playlists]
    assert "Subscribed" not in owned_names


def test_contract_add_tracks_batch_validation():
    """Test that add_tracks_batch returns valid AddResult."""
    provider = FakeProvider()
    playlist = provider.resolve_or_create_playlist("Test Playlist")
    
    # Test with empty batch
    result = provider.add_tracks_batch(playlist.id, [])
    assert result.added == 0
    assert result.duplicates == 0
    assert result.errors == 0
    
    # Test with single track
    result = provider.add_tracks_batch(playlist.id, ["spotify:track:test1"])
    assert result.added >= 0
    assert result.duplicates >= 0
    assert result.errors >= 0
    assert result.added + result.duplicates + result.errors == 1


def test_contract_track_entity_validation():
    """Test that Track entities have required fields."""
    provider = FakeProvider()
    
    playlists = list(provider.list_owned_playlists())
    if playlists:
        tracks = list(provider.list_tracks(playlists[0].id))
        
        for track in tracks:
            assert track.source_id is not None
            assert track.title is not None
            assert track.artists is not None
            assert len(track.artists) > 0
            assert track.duration_ms > 0


def test_contract_playlist_entity_validation():
    """Test that Playlist entities have required fields."""
    provider = FakeProvider()
    
    playlists = list(provider.list_owned_playlists())
    
    for playlist in playlists:
        assert playlist.id is not None
        assert playlist.name is not None
        assert playlist.owner_id is not None
        assert isinstance(playlist.is_owned, bool)


def test_contract_candidate_entity_validation():
    """Test that Candidate entities have required fields."""
    provider = FakeProvider()
    track = Track(source_id="t1", title="Test Song", artists=["Test Artist"], duration_ms=3000)
    
    candidates = provider.find_track_candidates(track)
    
    for candidate in candidates:
        assert candidate.uri is not None
        assert candidate.confidence is not None
        assert candidate.reason is not None


