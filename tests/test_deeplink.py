"""Deep link parsing - the old crash hotspot."""

from __future__ import annotations

import pytest

from services import deeplink


@pytest.mark.parametrize("payload", [None, "", "start", "  "])
def test_home(payload):
    assert deeplink.parse(payload).kind == deeplink.HOME


def test_plans():
    assert deeplink.parse("plans").kind == deeplink.PLANS


def test_verify_token():
    parsed = deeplink.parse("verify_abC123")
    assert parsed.kind == deeplink.VERIFY
    assert parsed.token == "abC123"
    assert parsed.resume == "verify_abC123"


def test_inline_verify():
    parsed = deeplink.parse("inline_verify")
    assert parsed.kind == deeplink.INLINE_VERIFY
    assert parsed.resume == ""


def test_file_payload_keeps_underscores_in_file_id():
    # file ids are urlsafe base64 - they may contain '-' and '_'
    parsed = deeplink.parse("file_-1001234567890_AbC-_dEf")
    assert parsed.kind == deeplink.FILE
    assert parsed.group_id == -1001234567890
    assert parsed.file_id == "AbC-_dEf"


def test_shortlink_payload():
    parsed = deeplink.parse("shortlink_-100_abc")
    assert parsed.kind == deeplink.SHORTLINK
    assert parsed.group_id == -100
    assert parsed.resume.startswith("shortlink_")


def test_all_payload():
    parsed = deeplink.parse("all_-1009876_xyz123")
    assert parsed.kind == deeplink.ALL
    assert parsed.group_id == -1009876
    assert parsed.key == "xyz123"


@pytest.mark.parametrize(
    "payload",
    ["garbage", "/start", "file_notanint_abc", "file_123", "all_123", "verify_"],
)
def test_unknown_never_raises(payload):
    parsed = deeplink.parse(payload)
    assert parsed.kind in (deeplink.UNKNOWN, deeplink.HOME)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("https://t.me/mychannel/42", ("mychannel", 42)),
        ("https://t.me/c/1234567/89", (-1001234567, 89)),
        ("join https://t.me/some_channel/7 now", ("some_channel", 7)),
        ("nothing here", None),
    ],
)
def test_parse_channel_link(text, expected):
    assert deeplink.parse_channel_link(text) == expected
