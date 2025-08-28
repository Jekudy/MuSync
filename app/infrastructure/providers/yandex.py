from typing import Iterable, List

from app.domain.entities import Playlist, Track, Candidate, AddResult
from app.domain.errors import RateLimited, TemporaryFailure, NotFound
from app.domain.ports import MusicProvider


class YandexMusicProvider(MusicProvider):
    """Yandex Music provider adapter implementing MusicProvider port.
    
    This adapter handles reading playlists and tracks from Yandex Music.
    For MVP, it only implements read operations (list_owned_playlists, list_tracks).
    Write operations (find_track_candidates, resolve_or_create_playlist, add_tracks_batch)
    are not implemented as Yandex Music is the source, not target.
    """

    def __init__(self, oauth_token: str):
        """Initialize the provider with OAuth token.
        
        Args:
            oauth_token: Yandex Music OAuth token
        """
        try:
            from yandex_music import Client
            self._client = Client(oauth_token).init()
            self._current_user = None
        except ImportError:
            raise RuntimeError("yandex-music library not installed")
        except Exception as e:
            raise TemporaryFailure(f"Failed to initialize Yandex Music client: {e}")

    def _get_current_user(self):
        """Get current user info, cached for performance."""
        if self._current_user is None:
            try:
                # Prefer explicit method if available for compatibility with tests
                if hasattr(self._client, 'users_me'):
                    self._current_user = self._client.users_me()
                else:
                    self._current_user = getattr(self._client, 'me')
            except Exception as e:
                raise TemporaryFailure(f"Failed to get current user: {e}")
        return self._current_user

    def list_owned_playlists(self) -> Iterable[Playlist]:
        """Return all playlists accessible to the current user.
        
        Returns:
            Iterable of Playlist entities, with is_owned flag set correctly
        """
        try:
            current_user = self._get_current_user()
            # Some clients expose uid directly, others via account.uid
            current_user_id = getattr(current_user, 'uid', None) or getattr(getattr(current_user, 'account', None), 'uid', None)
            playlists = self._client.users_playlists_list()
            
            for playlist in playlists:
                # Determine ownership based on owner ID
                is_owned = (
                    hasattr(playlist, 'owner') and 
                    hasattr(playlist.owner, 'uid') and
                    playlist.owner.uid == current_user_id
                )
                
                yield Playlist(
                    id=str(playlist.kind),
                    name=playlist.title,
                    owner_id=str(getattr(playlist.owner, 'uid', '')),
                    is_owned=is_owned,
                    track_count=playlist.track_count
                )
                
        except Exception as e:
            if "429" in str(e) or "Too many requests" in str(e):
                raise RateLimited(retry_after_ms=1000)  # Default 1 second
            elif "404" in str(e) or "not found" in str(e):
                raise NotFound(f"Playlists not found: {e}")
            else:
                raise TemporaryFailure(f"Failed to list playlists: {e}")

    def list_tracks(self, playlist_id: str) -> Iterable[Track]:
        """Iterate tracks belonging to the given playlist.
        
        Args:
            playlist_id: Yandex Music playlist ID (kind)
            
        Yields:
            Track entities with metadata from Yandex Music
        """
        try:
            current_user = self._get_current_user()
            playlist = self._client.users_playlists(playlist_id, user_id=current_user.account.uid)
            tracks = playlist.fetch_tracks()

            for t in tracks:
                # Yandex API may return TrackShort wrapper. Dereference only if
                # the wrapper lacks artists and the inner object has them.
                base = t
                try:
                    outer_artists = getattr(t, 'artists', None)
                    outer_ok = isinstance(outer_artists, (list, tuple)) and len(outer_artists) > 0
                    inner = getattr(t, 'track', None)
                    inner_artists = getattr(inner, 'artists', None) if inner is not None else None
                    inner_ok = isinstance(inner_artists, (list, tuple)) and len(inner_artists) > 0
                    if (not outer_ok) and inner is not None and inner_ok:
                        base = inner
                except Exception:
                    base = t

                # Extract artist names robustly
                artists = []
                base_artists = getattr(base, 'artists', None)
                if isinstance(base_artists, (list, tuple)):
                    for a in base_artists:
                        name = getattr(a, 'name', None)
                        if not name and isinstance(a, dict):
                            name = a.get('name')
                        if name:
                            artists.append(name)

                # Extract album title (first)
                album = None
                base_albums = getattr(base, 'albums', None)
                if base_albums:
                    first_album = base_albums[0]
                    album = getattr(first_album, 'title', None)
                    if not album and isinstance(first_album, dict):
                        album = first_album.get('title')

                # Extract duration in ms (fallbacks)
                duration_ms = getattr(base, 'duration_ms', None)
                if duration_ms is None:
                    # Some models expose duration in seconds
                    duration_sec = getattr(base, 'duration', None)
                    if duration_sec is not None:
                        try:
                            duration_ms = int(float(duration_sec) * 1000)
                        except Exception:
                            duration_ms = 0
                if duration_ms is None:
                    duration_ms = 0

                # Extract ISRC if available
                isrc = getattr(base, 'isrc', None)

                # Track id and title
                source_id = str(getattr(base, 'id', getattr(t, 'id', 'unknown')))
                title = getattr(base, 'title', getattr(t, 'title', ''))

                yield Track(
                    source_id=source_id,
                    title=title,
                    artists=artists,
                    duration_ms=int(duration_ms or 0),
                    album=album,
                    isrc=isrc
                )
                
        except Exception as e:
            if "429" in str(e) or "Too many requests" in str(e):
                raise RateLimited(retry_after_ms=1000)
            elif "404" in str(e) or "not found" in str(e):
                raise NotFound(f"Playlist {playlist_id} not found: {e}")
            else:
                raise TemporaryFailure(f"Failed to list tracks for playlist {playlist_id}: {e}")

    def find_track_candidates(self, track: Track, top_k: int = 3) -> List[Candidate]:
        """Not implemented for Yandex Music (source provider).
        
        This method is not implemented as Yandex Music is the source,
        not the target for track matching.
        """
        raise NotImplementedError(
            "Yandex Music is a source provider and does not support track search"
        )

    def list_liked_tracks(self) -> Iterable[Track]:
        """Return all liked tracks for the current user.
        
        Returns:
            Iterable of Track domain entities for user's liked tracks
        """
        try:
            likes = self._client.users_likes_tracks()
            full_tracks = likes.fetch_tracks()
            for track in full_tracks:
                try:
                    artists = [artist.name for artist in track.artists] if track.artists else []
                    album = track.albums[0].title if track.albums else None
                    isrc = getattr(track, 'isrc', None)
                    yield Track(
                        source_id=str(track.id),
                        title=track.title,
                        artists=artists,
                        duration_ms=int(getattr(track, 'duration_ms', 0) or 0),
                        album=album,
                        isrc=isrc
                    )
                except Exception:
                    continue
        except Exception as e:
            if "429" in str(e) or "Too many requests" in str(e):
                raise RateLimited(retry_after_ms=1000)
            elif "404" in str(e) or "not found" in str(e):
                raise NotFound(f"Liked tracks not found: {e}")
            else:
                raise TemporaryFailure(f"Failed to list liked tracks: {e}")

    def resolve_or_create_playlist(self, name: str) -> Playlist:
        """Not implemented for Yandex Music (source provider).
        
        This method is not implemented as Yandex Music is the source,
        not the target for playlist creation.
        """
        raise NotImplementedError(
            "Yandex Music is a source provider and does not support playlist creation"
        )

    def add_tracks_batch(self, playlist_id: str, track_uris: List[str]) -> AddResult:
        """Not implemented for Yandex Music (source provider).
        
        This method is not implemented as Yandex Music is the source,
        not the target for track addition.
        """
        raise NotImplementedError(
            "Yandex Music is a source provider and does not support track addition"
        )
