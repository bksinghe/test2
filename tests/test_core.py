"""Formatting, caching and duration parsing."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import pytest

from core.cache import TTLCache
from core.clock import as_utc, is_future, parse_duration, utcnow
from core.fmt import human_size, join_iterable, readable_time, shorten


# ------------------------------------------------------------------- cache
def test_cache_stores_and_expires():
    cache = TTLCache(ttl=0.05, maxsize=10)
    cache.set("a", 1)
    assert cache.get("a") == 1
    time.sleep(0.06)
    assert cache.get("a") is None


def test_cache_is_lru_bounded():
    cache = TTLCache(ttl=60, maxsize=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    assert "a" not in cache
    assert len(cache) == 2


def test_cache_getitem_raises():
    cache = TTLCache(ttl=60)
    with pytest.raises(KeyError):
        _ = cache["missing"]


# -------------------------------------------------------------- formatting
@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, "0 B"), (1023, "1023 B"), (1024, "1.00 KB"), (1536, "1.50 KB"), (5 * 1024**3, "5.00 GB")],
)
def test_human_size(value, expected):
    assert human_size(value) == expected


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0, "0s"), (-5, "0s"), (5, "5s"), (65, "1m5s"), (3725, "1h2m5s"), (90061, "1d1h1m1s")],
)
def test_readable_time(seconds, expected):
    assert readable_time(seconds) == expected


def test_join_iterable():
    assert join_iterable(None) == "N/A"
    assert join_iterable([]) == "N/A"
    assert join_iterable(["a"]) == "a"
    assert join_iterable(["a", "b"]) == "a, b"


def test_shorten():
    assert shorten("abc", 10) == "abc"
    assert shorten("abcdefghij", 6).endswith("...")


# ------------------------------------------------------------------- time
def test_parse_duration_accepts_units():
    assert parse_duration("1s") == 1
    assert parse_duration("30min") == 1800
    assert parse_duration("2 hours") == 7200
    assert parse_duration("1day") == 86400
    assert parse_duration("1month") == 86400 * 30
    assert parse_duration("1year") == 86400 * 365


@pytest.mark.parametrize("value", ["", "1", "day", "0day", "1fortnight", None])
def test_parse_duration_rejects_bad_input(value):
    assert parse_duration(value) is None


def test_as_utc_makes_naive_datetimes_comparable():
    naive = datetime(2030, 1, 1, 12, 0, 0)
    assert as_utc(naive).tzinfo == UTC
    assert is_future(as_utc(naive)) is True
    assert is_future(utcnow() - timedelta(days=1)) is False
    assert is_future(None) is False
