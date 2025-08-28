import os

import json
import time
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
from urllib3.exceptions import ReadTimeoutError

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from app.domain.entities import Track, Playlist, AddResult, Candidate
from app.domain.ports import MusicProvider
from app.domain.errors import RateLimited, TemporaryFailure, NotFound

logger = logging.getLogger(__name__)


class SpotifyProvider(MusicProvider):
    """Spotify music provider implementation."""
    
    def __init__(self, 
                 access_token: str,
                 refresh_token: str,
                 expires_at: Optional[datetime] = None,
                 client_id: Optional[str] = None,
                 client_secret: Optional[str] = None):
        """Initialize Spotify provider.
        
        Args:
            access_token: Spotify access token
            refresh_token: Spotify refresh token
            expires_at: Token expiration time
            client_id: Spotify client ID for token refresh
            client_secret: Spotify client secret for token refresh
        """
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at
        self.client_id = client_id or os.getenv('SPOTIFY_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('SPOTIFY_CLIENT_SECRET')
        
        # Initialize Spotify client with increased timeout
        # Allow tests to replace the underlying client by using a single attribute name
        _sp = __import__('spotipy')
        self._client = _sp.Spotify(
            auth=self.access_token
        )
        
        # Search configuration
        self._search_limit = int(os.getenv('MUSYNC_SEARCH_LIMIT', '20'))
        self._enable_title_only = os.getenv('MUSYNC_TITLE_ONLY_FALLBACK', '0') == '1'
        self._enable_translit = os.getenv('MUSYNC_TRANSLIT_FALLBACK', '0') == '1'
        self._market = os.getenv('MUSYNC_MARKET', 'RU')
        
        # Token refresh tracking
        self._last_refresh_attempt = 0
        self._refresh_cooldown = 5  # seconds between refresh attempts
    
    def _refresh_access_token(self) -> bool:
        """Refresh Spotify access token.
        
        Returns:
            True if token was refreshed successfully, False otherwise
        """
        current_time = time.time()
        
        # Prevent too frequent refresh attempts
        if current_time - self._last_refresh_attempt < self._refresh_cooldown:
            return False
        
        self._last_refresh_attempt = current_time
        
        if not self.client_id or not self.client_secret:
            logger.warning("Cannot refresh token: missing client credentials")
            return False
        
        try:
            logger.info("Refreshing Spotify access token...")
            
            # Create OAuth manager for token refresh
            oauth_manager = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=os.getenv('SPOTIFY_REDIRECT_URI', 'http://localhost:8080/callback'),
                scope='playlist-modify-public playlist-modify-private'
            )
            
            # Refresh the token
            token_info = oauth_manager.refresh_access_token(self.refresh_token)
            
            if token_info and 'access_token' in token_info:
                self.access_token = token_info['access_token']
                
                # Update refresh token if a new one was provided
                if 'refresh_token' in token_info:
                    self.refresh_token = token_info['refresh_token']
                
                # Update expiration time
                if 'expires_at' in token_info:
                    self.expires_at = datetime.fromtimestamp(token_info['expires_at'])
                
                # Update the Spotify client with new token
                self._client = spotipy.Spotify(
                    auth=self.access_token,
                    requests_timeout=15
                )
                
                # Update tokens in user_tokens.json
                self._update_tokens_file()
                
                logger.info("Spotify access token refreshed successfully")
                return True
            else:
                logger.error("Failed to refresh token: invalid response")
                return False
                
        except Exception as e:
            logger.error(f"Failed to refresh Spotify token: {e}")
            return False
    
    def _update_tokens_file(self) -> None:
        """Update tokens in user_tokens.json file."""
        try:
            tokens_file = "user_tokens.json"
            if os.path.exists(tokens_file):
                with open(tokens_file, 'r') as f:
                    tokens_data = json.load(f)
            else:
                tokens_data = {}
            
            # Update Spotify tokens
            if 'spotify' not in tokens_data:
                tokens_data['spotify'] = {}
            
            tokens_data['spotify']['access_token'] = self.access_token
            tokens_data['spotify']['refresh_token'] = self.refresh_token
            if self.expires_at:
                tokens_data['spotify']['expires_at'] = self.expires_at.isoformat()
            
            # Write back to file
            with open(tokens_file, 'w') as f:
                json.dump(tokens_data, f, indent=2)
                
            logger.debug("Updated tokens in user_tokens.json")
            
        except Exception as e:
            logger.warning(f"Failed to update tokens file: {e}")
    
    def _handle_spotify_error(self, error: Exception, operation: str) -> bool:
        """Handle Spotify API errors with automatic token refresh.
        
        Args:
            error: The exception that occurred
            operation: Description of the operation being performed
        Returns:
            True if token was refreshed and operation can be retried, False otherwise
        """
        if hasattr(error, 'http_status') and error.http_status == 401:
            logger.warning(f"Spotify token expired during {operation}, attempting refresh...")
            if self._refresh_access_token():
                logger.info("Token refreshed, operation can be retried")
                return True
            else:
                logger.error("Failed to refresh token, operation cannot continue")
                return False
        else:
            # Re-raise other errors
            raise error

    def _spotify_track_to_domain(self, spotify_track: Dict[str, Any]) -> Optional[Track]:
        """Convert Spotify track to domain Track entity.
        
        Args:
            spotify_track: Spotify track object
            
        Returns:
            Domain Track entity or None if conversion fails
        """
        try:
            # Extract basic track info
            track_id = spotify_track.get('id')
            title = spotify_track.get('name', '')
            duration_ms = spotify_track.get('duration_ms', 0)
            
            # Extract artist info
            artists = spotify_track.get('artists', [])
            artist_names = [artist.get('name', '') for artist in artists if artist.get('name')]
            
            # Extract album info
            album = spotify_track.get('album', {})
            album_title = album.get('name', '') if album else ''
            
            # Extract ISRC
            external_ids = spotify_track.get('external_ids', {})
            isrc = external_ids.get('isrc', '')
            
            # Create domain track
            return Track(
                id=track_id,
                source_id=track_id or '',
                title=title,
                artists=artist_names,
                duration_ms=duration_ms,
                isrc=isrc,
                album=album_title,
                uri=f"spotify:track:{track_id}" if track_id else None
            )
            
        except Exception as e:
            logger.warning(f"Failed to convert Spotify track to domain: {e}")
            return None

    def list_owned_playlists(self) -> List[Playlist]:
        """List playlists owned by the current user.
        
        Returns:
            List of owned playlists
        """
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                # Get current user
                current_user = self._client.current_user()
                user_id = current_user['id']
                
                # Get user's playlists
                playlists = []
                offset = 0
                limit = 50
                
                while True:
                    user_playlists = self._client.current_user_playlists(limit=limit, offset=offset)
                    
                    if not user_playlists or 'items' not in user_playlists:
                        break
                    
                    for playlist in user_playlists['items']:
                        # Check if playlist is owned by current user
                        owner_id = playlist.get('owner', {}).get('id', '')
                        if owner_id == user_id:
                            playlists.append(Playlist(
                                id=playlist['id'],
                                name=playlist['name'],
                                owner_id=owner_id,
                                is_owned=True,
                                track_count=playlist.get('tracks', {}).get('total', 0)
                            ))
                    
                    # Check if we've got all playlists
                    if len(user_playlists['items']) < limit:
                        break
                    
                    offset += limit
                
                return playlists
                
            except Exception as e:
                if attempt < max_retries and self._handle_spotify_error(e, "list_owned_playlists"):
                    # Token was refreshed, retry the operation
                    continue
                else:
                    logger.error(f"Failed to list owned playlists: {e}")
                    raise TemporaryFailure(f"Failed to list playlists: {e}")

    def list_tracks(self, playlist_id: str) -> List[Track]:
        """List tracks in a playlist.
        
        Args:
            playlist_id: Playlist ID
            
        Returns:
            List of tracks in the playlist
        """
        try:
            tracks = []
            offset = 0
            limit = 100
            
            while True:
                try:
                    playlist_tracks = self._client.playlist_tracks(
                        playlist_id, 
                        limit=limit, 
                        offset=offset,
                        fields='items(track(id,name,artists,album,duration_ms,external_ids))'
                    )
                    
                    if not playlist_tracks or 'items' not in playlist_tracks:
                        break
                    
                    for item in playlist_tracks['items']:
                        track_data = item.get('track')
                        if track_data and track_data.get('id'):
                            domain_track = self._spotify_track_to_domain(track_data)
                            if domain_track:
                                tracks.append(domain_track)
                    
                    # Check if we've got all tracks
                    if len(playlist_tracks['items']) < limit:
                        break
                    
                    offset += limit
                    
                except Exception as e:
                    if hasattr(e, 'http_status') and e.http_status == 401:
                        self._handle_spotify_error(e, "list playlist tracks")
                        # Retry with refreshed token
                        continue
                    else:
                        raise
            
            return tracks
            
        except Exception as e:
            logger.error(f"Failed to list tracks for playlist {playlist_id}: {e}")
            raise TemporaryFailure(f"Failed to list playlist tracks: {e}")

    def find_track_candidates(self, track: Track, top_k: int = 3) -> List[Candidate]:
        """Find track candidates in Spotify.
        
        Args:
            track: Track to search for
            top_k: Maximum number of candidates to return
            
        Returns:
            List of candidate tracks
        """
        candidates = []
        
        # Multi-pass search strategy
        search_queries = []
        
        # Pass 1: ISRC search (if available)
        if track.isrc:
            search_queries.append(('isrc', track.isrc))
        
        # Pass 2: Strict title + artist search
        if track.title and track.artists:
            primary_artist = track.artists[0]  # Use first artist
            search_queries.append(('strict', f'track:"{track.title}" artist:"{primary_artist}"'))
        
        # Pass 3: Free-text title + artist search
        if track.title and track.artists:
            primary_artist = track.artists[0]  # Use first artist
            search_queries.append(('free_text', f'{track.title} {primary_artist}'))
        
        # Pass 4: Title-only search (if enabled)
        if self._enable_title_only and track.title:
            search_queries.append(('title_only', track.title))
        
        # Pass 5: Translit fallback (if enabled)
        if self._enable_translit and track.title:
            # Simple transliteration for common Cyrillic characters
            translit_map = {
                'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
                'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
                'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
                'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
                'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
            }
            
            translit_title = track.title.lower()
            for cyrillic, latin in translit_map.items():
                translit_title = translit_title.replace(cyrillic, latin)
            
            search_queries.append(('translit', translit_title))
        
        # Execute search queries
        for search_type, query in search_queries:
            try:
                if not query.strip():  # Skip empty queries
                    continue
                
                logger.debug(f"Searching with {search_type}: {query} (market={self._market}, limit={self._search_limit})")
                
                if search_type == 'isrc':
                    results = self._client.search(f'isrc:{query}', type='track', limit=self._search_limit, market=self._market)
                else:
                    results = self._client.search(query, type='track', limit=self._search_limit, market=self._market)
                
                if results and 'tracks' in results and 'items' in results['tracks']:
                    for idx, item in enumerate(results['tracks']['items']):
                        candidate = self._spotify_track_to_candidate(item, search_type, track, rank=idx)
                        if candidate and candidate not in candidates:
                            candidates.append(candidate)
                            if search_type == 'isrc':
                                # ISRC exact match sufficient
                                return candidates[:1]
                            if len(candidates) >= top_k:
                                break
                
                if len(candidates) >= top_k:
                    break
                    
            except ReadTimeoutError:
                logger.warning(f"Read timeout during {search_type} search for track '{track.title}'")
                # Continue with next search strategy instead of failing
                continue
            except Exception as e:
                status = getattr(e, 'status_code', None)
                if status == 429:
                    raise RateLimited(retry_after_ms=1000)
                if status is not None:
                    try:
                        if int(status) >= 500:
                            raise TemporaryFailure(str(e))
                    except Exception:
                        pass
                if hasattr(e, 'http_status') and e.http_status == 401:
                    self._handle_spotify_error(e, f"{search_type} search")
                    continue
                raise TemporaryFailure(str(e))
        
        # If no candidates found, create a timeout result
        if not candidates:
            logger.warning(f"No candidates found for track '{track.title}' by '{track.artists[0] if track.artists else 'Unknown'}'")
        else:
            # Log top candidates for diagnostics
            top = candidates[:min(len(candidates), 3)]
            for c in top:
                logger.debug(f"Candidate: uri={c.uri} conf={c.confidence:.3f} reason={c.reason} title={getattr(c,'title',None)} artists={getattr(c,'artists',None)} album={getattr(c,'album',None)} dur={getattr(c,'duration_ms',None)} rank={getattr(c,'rank',None)}")
            # Return empty list - the matcher will handle this as not_found
        
        # Sort by confidence desc before returning
        candidates_sorted = sorted(candidates, key=lambda c: c.confidence, reverse=True)
        return candidates_sorted[:top_k]

    def _spotify_track_to_candidate(self, spotify_track: Dict[str, Any], search_type: str, source_track: Track, rank: Optional[int] = None) -> Optional[Candidate]:
        """Convert Spotify track to Candidate entity.
        
        Args:
            spotify_track: Spotify track object
            search_type: Type of search that found this track
            source_track: Original source track for comparison
            
        Returns:
            Candidate entity or None if conversion fails
        """
        try:
            # Extract basic track info
            track_id = spotify_track.get('id')
            title = spotify_track.get('name', '')
            duration_ms = spotify_track.get('duration_ms', 0)
            
            # Extract artist info
            artists = spotify_track.get('artists', [])
            artist_names = [artist.get('name', '') for artist in artists if artist.get('name')]
            
            # Calculate confidence based on search type and similarity
            confidence = self._calculate_confidence(source_track, title, artist_names, duration_ms, search_type)
            
            # Determine reason
            if search_type == 'isrc':
                reason = 'isrc_exact'
            elif confidence >= 0.95:
                reason = 'exact_match'
            else:
                reason = 'fuzzy_match'
            
            # Extract album info
            album = spotify_track.get('album', {})
            album_title = album.get('name', '') if album else ''
            album_type = album.get('album_type', None) if album else None

            # Build URI from field or id
            uri_field = spotify_track.get('uri')
            uri_value = uri_field or (f"spotify:track:{track_id}" if track_id else None)

            # Create candidate with metadata and rank
            return Candidate(
                uri=uri_value,
                confidence=confidence,
                reason=reason,
                title=title,
                artists=artist_names,
                album=album_title,
                duration_ms=duration_ms,
                rank=rank,
                album_type=album_type
            )
            
        except Exception as e:
            logger.warning(f"Failed to convert Spotify track to candidate: {e}")
            return None
    
    def _calculate_confidence(self, source_track: Track, target_title: str, target_artists: List[str], target_duration_ms: int, search_type: str) -> float:
        """Calculate confidence score for a candidate match.
        
        Args:
            source_track: Original source track
            target_title: Target track title
            target_artists: Target track artists
            target_duration_ms: Target track duration
            search_type: Type of search used
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        # ISRC matches are always exact
        if search_type == 'isrc':
            return 1.0
        
        # Title similarity
        title_similarity = self._string_similarity(source_track.title.lower(), target_title.lower())
        
        # Artist similarity (compare with first artist)
        artist_similarity = 0.0
        if source_track.artists and target_artists:
            source_artist = source_track.artists[0].lower()
            target_artist = target_artists[0].lower()
            artist_similarity = self._string_similarity(source_artist, target_artist)
        
        # Duration similarity
        duration_diff = abs(source_track.duration_ms - target_duration_ms)
        duration_similarity = 1.0 if duration_diff <= 2000 else max(0.0, 1.0 - (duration_diff - 2000) / 3000)
        
        # Weighted average
        confidence = (title_similarity * 0.5 + artist_similarity * 0.4 + duration_similarity * 0.1)
        
        return min(1.0, confidence)
    
    def _string_similarity(self, str1: str, str2: str) -> float:
        """Calculate simple string similarity using character overlap."""
        if not str1 or not str2:
            return 0.0
        
        # Simple Jaccard similarity
        set1 = set(str1)
        set2 = set(str2)
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0

    def resolve_or_create_playlist(self, name: str) -> Playlist:
        """Resolve existing playlist by name or create new one.
        
        Args:
            name: Playlist name
            
        Returns:
            Playlist entity
        """
        try:
            # First, try to find existing playlist
            playlists = self.list_owned_playlists()
            
            for playlist in playlists:
                if playlist.name.lower() == name.lower():
                    logger.info(f"Found existing playlist: {name}")
                    return playlist
            
            # Create new playlist if not found
            logger.info(f"Creating new playlist: {name}")
            
            try:
                result = self._client.user_playlist_create(
                    self._client.current_user()['id'],
                    name,
                    public=False
                )
                
                return Playlist(
                    id=result['id'],
                    name=result['name'],
                    owner_id=result['owner']['id'],
                    is_owned=True,
                    track_count=0
                )
                
            except Exception as e:
                if hasattr(e, 'http_status') and e.http_status == 401:
                    self._handle_spotify_error(e, "create playlist")
                    # Retry with refreshed token
                    result = self._client.user_playlist_create(
                        self._client.current_user()['id'],
                        name,
                        public=False
                    )
                    
                    return Playlist(
                        id=result['id'],
                        name=result['name'],
                        owner_id=result['owner']['id'],
                        is_owned=True,
                        track_count=0
                    )
                else:
                    raise
                    
        except Exception as e:
            logger.error(f"Failed to resolve or create playlist '{name}': {e}")
            raise TemporaryFailure(f"Failed to resolve or create playlist: {e}")

    def add_tracks_batch(self, playlist_id: str, track_uris: List[str]) -> AddResult:
        """Add multiple tracks to a playlist.
        
        Args:
            playlist_id: Target playlist ID
            track_uris: List of track URIs to add
            
        Returns:
            AddResult with operation statistics
        """
        if not track_uris:
            return AddResult(added=0, duplicates=0, errors=0)
        
        try:
            # Spotify allows up to 100 tracks per request
            batch = track_uris[:100]
            total_added = 0
            total_duplicates = 0
            total_errors = 0
            
            try:
                # Add tracks to playlist
                result = self._client.playlist_add_items(playlist_id, batch)
                
                # Parse result
                if result and 'snapshot_id' in result:
                    total_added += len(batch)
                else:
                    total_errors += len(batch)
                    
            except Exception as e:
                if hasattr(e, 'http_status') and e.http_status == 401:
                    self._handle_spotify_error(e, "add tracks batch")
                    # Retry with refreshed token
                    try:
                        result = self._client.playlist_add_items(playlist_id, batch)
                        if result and 'snapshot_id' in result:
                            total_added += len(batch)
                        else:
                            total_errors += len(batch)
                    except Exception as retry_error:
                        logger.error(f"Retry failed for add tracks batch: {retry_error}")
                        total_errors += len(batch)
                elif hasattr(e, 'http_status') and e.http_status == 429:
                    # Rate limited
                    retry_after = int(getattr(e, 'headers', {}).get('Retry-After', 1)) if hasattr(e, 'headers') else 1
                    raise RateLimited(retry_after_ms=retry_after * 1000)
                else:
                    msg = str(e)
                    if 'not found' in msg.lower():
                        raise NotFound(msg)
                    logger.error(f"Failed to add tracks batch: {e}")
                    total_errors += len(batch)
            
            return AddResult(
                added=total_added,
                duplicates=total_duplicates,
                errors=total_errors
            )
        
        except RateLimited:
            raise
        except NotFound:
            raise
        except Exception as e:
            logger.error(f"Failed to add tracks batch: {e}")
            raise TemporaryFailure(f"Failed to add tracks: {e}")

    def add_likes_batch(self, track_uris: List[str]) -> AddResult:
        """Add multiple tracks to user's liked songs.
        
        Args:
            track_uris: List of track URIs to add
            
        Returns:
            AddResult with operation statistics
        """
        if not track_uris:
            return AddResult(added=0, duplicates=0, errors=0)
        
        try:
            # Convert URIs to track IDs
            track_ids = []
            for uri in track_uris:
                if uri.startswith('spotify:track:'):
                    track_id = uri.replace('spotify:track:', '')
                    track_ids.append(track_id)
            
            if not track_ids:
                return AddResult(added=0, duplicates=0, errors=0)
            
            # Spotify allows up to 50 tracks per request for likes
            batch_size = 50
            total_added = 0
            total_duplicates = 0
            total_errors = 0
            
            for i in range(0, len(track_ids), batch_size):
                batch = track_ids[i:i + batch_size]
                
                try:
                    # Add tracks to liked songs
                    self._client.current_user_saved_tracks_add(batch)
                    total_added += len(batch)
                    
                except Exception as e:
                    if hasattr(e, 'http_status') and e.http_status == 401:
                        self._handle_spotify_error(e, "add likes batch")
                        # Retry with refreshed token
                        try:
                            self._client.current_user_saved_tracks_add(batch)
                            total_added += len(batch)
                        except Exception as retry_error:
                            logger.error(f"Retry failed for add likes batch: {retry_error}")
                            total_errors += len(batch)
                    elif hasattr(e, 'http_status') and e.http_status == 429:
                        # Rate limited
                        retry_after = int(e.headers.get('Retry-After', 1)) if hasattr(e, 'headers') else 1
                        raise RateLimited(retry_after_ms=retry_after * 1000)
                    else:
                        logger.error(f"Failed to add likes batch: {e}")
                        total_errors += len(batch)
            
            return AddResult(
                added=total_added,
                duplicates=total_duplicates,
                errors=total_errors
            )
            
        except RateLimited:
            raise
        except Exception as e:
            logger.error(f"Failed to add likes batch: {e}")
            raise TemporaryFailure(f"Failed to add likes: {e}")

    # Backwards-compatibility alias used by CLI likes flow
    def add_saved_tracks_batch(self, track_uris: List[str]) -> AddResult:
        """Alias to add tracks to user's library (liked songs)."""
        return self.add_likes_batch(track_uris)
