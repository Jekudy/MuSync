from typing import List, Optional
from dataclasses import dataclass

import os
from typing import Optional, List
from app.domain.entities import Track, Candidate
from app.domain.normalization import normalize_string, normalize_artists_joined

def _tokenize_artist_names(artists: List[str]) -> set[str]:
    """Normalize artist names and tokenize into a flat set of significant tokens.
    Tail/service tokens like numerical-only and common suffixes are ignored.
    """
    if not artists:
        return set()
    normalized = normalize_artists_joined(artists)
    tokens = set(normalized.split())
    tail_tokens = {"vol", "pt", "remaster", "remastered", "live", "edit"}
    filtered: set[str] = set()
    for tok in tokens:
        if not tok:
            continue
        if tok.isdigit():
            continue
        if tok in tail_tokens:
            continue
        filtered.add(tok)
    return filtered


@dataclass
class MatchResult:
    """Result of track matching operation."""
    
    uri: Optional[str]
    confidence: float
    reason: str


class TrackMatcher:
    """Track matching algorithm for finding the best match between source and target tracks.
    
    This matcher implements a multi-strategy approach:
    1. ISRC exact match (confidence 1.0)
    2. Title + artist + duration exact match (confidence ≥0.95)
    3. Fuzzy match (confidence ≥0.85)
    
    The matcher also handles ambiguous cases and not found scenarios.
    """
    
    def __init__(self, 
                 exact_threshold: float = 0.95,
                 fuzzy_threshold: float = 0.85,
                 ambiguous_threshold: float = 0.05,
                 allow_ambiguous_best: bool = False):
        """Initialize the matcher with configurable thresholds.
        
        Args:
            exact_threshold: Minimum confidence for exact matches
            fuzzy_threshold: Minimum confidence for fuzzy matches
            ambiguous_threshold: Maximum difference between top candidates to avoid ambiguity
            allow_ambiguous_best: If True, return best candidate even when ambiguity is detected
        """
        self.exact_threshold = exact_threshold
        self.fuzzy_threshold = fuzzy_threshold
        self.ambiguous_threshold = ambiguous_threshold
        self.allow_ambiguous_best = allow_ambiguous_best

    def find_best_match(self, source_track: Track, candidates: List[Candidate]) -> MatchResult:
        """Find the best match for a source track among candidates.
        
        Args:
            source_track: Source track to find match for
            candidates: List of candidate tracks from target provider
            
        Returns:
            MatchResult with the best match or not_found/ambiguous
        """
        if not candidates:
            return MatchResult(
                uri=None,
                confidence=0.0,
                reason="not_found"
            )
        
        # New selection strategy: prefer metadata-based rules; fallback to confidence order
        # 1) Full-text title equality + artist-overlap ≥1
        source_title_n = normalize_string(source_track.title)
        source_artist_tokens = _tokenize_artist_names(source_track.artists)

        def artist_overlap_ok(candidate_artists: Optional[List[str]]) -> bool:
            cand_tokens = _tokenize_artist_names(candidate_artists or [])
            return len(source_artist_tokens.intersection(cand_tokens)) >= 1 if source_artist_tokens else bool(cand_tokens)

        # Filter candidates that have metadata available
        meta_candidates = [c for c in candidates if hasattr(c, 'title') and hasattr(c, 'artists')]

        def normalize_album(a: Optional[str]) -> str:
            return normalize_string(a or "")

        selected: Candidate | None = None
        if meta_candidates and source_track.title and source_track.artists:
            full_text = []
            for c in meta_candidates:
                try:
                    c_title_n = normalize_string(getattr(c, 'title', '') or '')
                    if c_title_n == source_title_n and artist_overlap_ok(getattr(c, 'artists', None)):
                        full_text.append(c)
                except Exception:
                    continue
            pool = full_text if full_text else [c for c in meta_candidates if artist_overlap_ok(getattr(c, 'artists', None))]
            if pool:
                # Tie-break: album match (if source has album)
                if source_track.album:
                    src_album_n = normalize_album(source_track.album)
                    album_matched = [c for c in pool if normalize_album(getattr(c, 'album', None)) == src_album_n]
                    if album_matched:
                        pool = album_matched
                # Tie-break: rank (ascending), then fall back to confidence desc
                def rank_key(c: Candidate):
                    rank = getattr(c, 'rank', None)
                    return (rank if isinstance(rank, int) else 10**9, )
                pool_sorted = sorted(pool, key=lambda c: (rank_key(c), -c.confidence))
                selected = pool_sorted[0]

        if selected is None:
            # Fallback: preserve previous behavior but without low-confidence rejection and without ambiguity stop
            sorted_candidates = sorted(candidates, key=lambda c: c.confidence, reverse=True)
            selected = sorted_candidates[0]

        # Risk-mode minimal gating on confidence
        risk_mode = os.getenv('MUSYNC_RISK_MODE', 'strict').lower()
        min_conf = 0.0
        if risk_mode == 'strict':
            min_conf = self.fuzzy_threshold  # 0.85 by default
        elif risk_mode == 'balanced':
            min_conf = 0.80

        if selected.confidence < min_conf:
            return MatchResult(uri=None, confidence=0.0, reason="not_found")

        return MatchResult(
            uri=selected.uri,
            confidence=selected.confidence,
            reason=selected.reason
        )

    def match_tracks_batch(self, source_tracks: List[Track], 
                          target_provider_candidates: List[List[Candidate]]) -> List[MatchResult]:
        """Match multiple tracks in batch.
        
        Args:
            source_tracks: List of source tracks
            target_provider_candidates: List of candidate lists for each source track
            
        Returns:
            List of match results corresponding to source tracks
        """
        if len(source_tracks) != len(target_provider_candidates):
            raise ValueError("Number of source tracks must match number of candidate lists")
        
        results = []
        for source_track, candidates in zip(source_tracks, target_provider_candidates):
            result = self.find_best_match(source_track, candidates)
            results.append(result)
        
        return results

    def calculate_match_rate(self, results: List[MatchResult]) -> float:
        """Calculate the overall match rate from results.
        
        Args:
            results: List of match results
            
        Returns:
            Match rate as a percentage (0.0 to 1.0)
        """
        if not results:
            return 0.0
        
        successful_matches = sum(1 for r in results if r.uri is not None)
        return successful_matches / len(results)

    def calculate_false_match_rate(self, results: List[MatchResult], 
                                  expected_uris: List[Optional[str]]) -> float:
        """Calculate the false match rate by comparing with expected URIs.
        
        Args:
            results: List of actual match results
            expected_uris: List of expected URIs (None for not_found)
            
        Returns:
            False match rate as a percentage (0.0 to 1.0)
        """
        if len(results) != len(expected_uris):
            raise ValueError("Number of results must match number of expected URIs")
        
        if not results:
            return 0.0
        
        false_matches = 0
        total_matches = 0
        
        for result, expected_uri in zip(results, expected_uris):
            if result.uri is not None:
                total_matches += 1
                if expected_uri is not None and result.uri != expected_uri:
                    false_matches += 1
        
        if total_matches == 0:
            return 0.0
        
        return false_matches / total_matches

    def get_match_statistics(self, results: List[MatchResult]) -> dict:
        """Get detailed statistics about match results.
        
        Args:
            results: List of match results
            
        Returns:
            Dictionary with match statistics
        """
        total = len(results)
        if total == 0:
            return {
                "total": 0,
                "matched": 0,
                "not_found": 0,
                "ambiguous": 0,
                "match_rate": 0.0,
                "by_reason": {}
            }
        
        matched = sum(1 for r in results if r.uri is not None)
        not_found = sum(1 for r in results if r.reason == "not_found")
        ambiguous = sum(1 for r in results if r.reason == "ambiguous")
        
        # Count by reason
        by_reason = {}
        for result in results:
            reason = result.reason
            by_reason[reason] = by_reason.get(reason, 0) + 1
        
        return {
            "total": total,
            "matched": matched,
            "not_found": not_found,
            "ambiguous": ambiguous,
            "match_rate": matched / total,
            "by_reason": by_reason
        }
