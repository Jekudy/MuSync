from __future__ import annotations

import re
import unicodedata
from typing import Iterable

from .entities import Track


_FEAT_PATTERN = re.compile(r"\b(feat\.?|ft\.)\b", re.IGNORECASE)
_PARENS_CHARS_PATTERN = re.compile(r"[\(\)\[\]\{\}]")
_PARENS_CONTENT_PATTERN = re.compile(r"\s*[\(\[\{][^\)\]\}]*[\)\]\}]\s*")
# Keep all unicode word characters and spaces; strip punctuation/symbols. Then remove underscores separately.
_NON_WORD_SPACE_PATTERN = re.compile(r"[^\w\s]", re.UNICODE)
_MULTISPACE_PATTERN = re.compile(r"\s+")
_TAIL_TOKENS = {
    "vol", "pt", "remaster", "remastered", "live", "edit",
}


def _strip_diacritics(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def normalize_string(value: str) -> str:
    value = value or ""
    value = _strip_diacritics(value)
    value = value.lower()
    value = value.replace("&", " and ")
    value = _FEAT_PATTERN.sub(" ", value)
    # Remove parenthetical/bracketed content entirely
    while True:
        new_value = _PARENS_CONTENT_PATTERN.sub(" ", value)
        if new_value == value:
            break
        value = new_value
    # Remove any leftover bracket characters
    value = _PARENS_CHARS_PATTERN.sub(" ", value)
    value = _NON_WORD_SPACE_PATTERN.sub(" ", value)
    # Replace underscores that \w preserved
    value = value.replace("_", " ")
    value = _MULTISPACE_PATTERN.sub(" ", value).strip()
    return value


def normalize_artists_joined(artists: Iterable[str]) -> str:
    def _strip_leading_articles(name: str) -> str:
        if name.startswith("the "):
            return name[4:]
        return name

    normalized = sorted(
        _strip_leading_articles(normalize_string(a)) for a in artists if a
    )
    return " ".join(n for n in normalized if n)


def normalize_artist_tokens(artists: Iterable[str]) -> list[str]:
    """Normalize artist names and return a list of significant tokens.
    Drops numeric-only and common tail/service tokens like 'vol', 'pt', 'remaster', 'live', 'edit'.
    """
    tokens: list[str] = []
    for artist in artists or []:
        norm = normalize_string(artist)
        for tok in norm.split():
            if not tok:
                continue
            if tok.isdigit():
                continue
            if tok in _TAIL_TOKENS:
                continue
            tokens.append(tok)
    return tokens


def round_duration_ms(duration_ms: int, tolerance_ms: int = 2000) -> int:
    if duration_ms < 0:
        return 0
    bucket = max(1, tolerance_ms)
    # Round to nearest bucket (e.g., 2000ms groups)
    return int(round(duration_ms / bucket)) * bucket


def build_track_key(track: Track, tolerance_ms: int = 2000) -> str:
    if track.isrc:
        return f"isrc:{track.isrc}"
    title_n = normalize_string(track.title)
    artists_n = normalize_artists_joined(track.artists)
    dur_r = round_duration_ms(track.duration_ms, tolerance_ms=tolerance_ms)
    return f"meta:{title_n}::{artists_n}::{dur_r}"


