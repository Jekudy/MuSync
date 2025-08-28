from app.domain.entities import Track


def test_normalize_string_basic_cases():
    from app.domain.normalization import normalize_string

    assert normalize_string("Hello World") == "hello world"
    assert normalize_string("Héllo Wörld!") == "hello world"
    assert normalize_string("Song (Live)") == "song"
    assert normalize_string("Artist feat. Someone") == "artist someone"
    assert normalize_string("A & B") == "a and b"


def test_normalize_artists_joined_is_order_insensitive():
    from app.domain.normalization import normalize_artists_joined

    a = normalize_artists_joined(["The Beatles", "John Lennon"])  # => "beatles john lennon"
    b = normalize_artists_joined(["john lennon", "beatles"])  # same set, different order/case
    assert a == b


def test_round_duration_ms_tolerance():
    from app.domain.normalization import round_duration_ms

    assert round_duration_ms(1999, tolerance_ms=2000) == 2000
    assert round_duration_ms(2001, tolerance_ms=2000) == 2000
    assert round_duration_ms(3000, tolerance_ms=2000) == 4000


def test_build_track_key_prefers_isrc_when_present():
    from app.domain.normalization import build_track_key

    t_with_isrc = Track(
        source_id="y1",
        title="Song",
        artists=["A"],
        duration_ms=2010,
        isrc="USABC1234567",
    )
    t_without_isrc = Track(
        source_id="y2",
        title="Song",
        artists=["A"],
        duration_ms=2010,
        isrc=None,
    )

    key_isrc = build_track_key(t_with_isrc)
    key_no_isrc = build_track_key(t_without_isrc)

    assert key_isrc == "isrc:USABC1234567"
    assert key_no_isrc.startswith("meta:")
    assert "song" in key_no_isrc
    assert "a" in key_no_isrc
    assert key_no_isrc.endswith(":2000")


def test_normalize_artist_tokens_ignores_tail_tokens_and_numbers():
    from app.domain.normalization import normalize_artist_tokens

    artists = [
        "Артист №7",
        "Band Vol. 2",
        "Singer pt. II",
        "Name (Remaster)",
        "Performer - Live Edit",
    ]
    tokens = normalize_artist_tokens(artists)
    # Should remove 'vol', 'pt', 'remaster', 'live', 'edit' and numeric-only tokens like '7' or '2'
    assert "vol" not in tokens
    assert "pt" not in tokens
    assert "remaster" not in tokens
    assert "live" not in tokens
    assert "edit" not in tokens
    assert "7" not in tokens and "2" not in tokens
    # Should still contain meaningful name tokens
    assert any(t for t in tokens if t in {"артист", "band", "singer", "name", "performer"})

