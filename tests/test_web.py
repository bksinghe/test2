"""HTTP range handling for the streaming endpoint."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from web.routes import _range


class FakeRequest(SimpleNamespace):
    def __init__(self, headers=None, start=None, stop=None):
        super().__init__(
            headers=headers or {},
            http_range=SimpleNamespace(start=start, stop=stop),
        )


def test_full_file_without_range():
    assert _range(FakeRequest(), 1000) == (0, 999)


def test_explicit_range_header():
    request = FakeRequest(headers={"Range": "bytes=100-199"})
    assert _range(request, 1000) == (100, 199)


def test_open_ended_range():
    request = FakeRequest(headers={"Range": "bytes=500-"})
    assert _range(request, 1000) == (500, 999)


def test_range_is_clamped_to_file_size():
    request = FakeRequest(headers={"Range": "bytes=900-5000"})
    assert _range(request, 1000) == (900, 999)


def test_garbage_range_falls_back_to_whole_file():
    request = FakeRequest(headers={"Range": "bytes=abc-def"})
    assert _range(request, 1000) == (0, 999)


@pytest.mark.parametrize(("start", "stop"), [(None, None), (0, 100), (50, None)])
def test_http_range_object(start, stop):
    request = FakeRequest(start=start, stop=stop)
    low, high = _range(request, 1000)
    assert 0 <= low <= high <= 999
