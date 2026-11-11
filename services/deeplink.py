"""``/start`` payload parsing.

Pure functions only - this is the part that used to explode with
``ValueError``/``IndexError`` for unexpected payloads, so it is heavily unit
tested in ``tests/test_deeplink.py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

PRIVATE_LINK = re.compile(r"https?://t\.me/c/(\d+)/(\d+)")
PUBLIC_LINK = re.compile(r"https?://t\.me/([A-Za-z0-9_]{4,})/(\d+)")

HOME = "home"
PLANS = "plans"
VERIFY = "verify"
INLINE_VERIFY = "inline_verify"
FILE = "file"
SHORTLINK = "shortlink"
ALL = "all"
UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class StartPayload:
    kind: str = HOME
    group_id: int | None = None
    file_id: str = ""
    key: str = ""
    token: str = ""
    resume: str = ""

    @property
    def is_delivery(self) -> bool:
        return self.kind in (FILE, SHORTLINK, ALL)


def _int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse(payload: str | None) -> StartPayload:
    """Parse a ``?start=`` payload without ever raising."""
    raw = (payload or "").strip()

    if raw in ("", "start"):
        return StartPayload(kind=HOME)
    if raw == "plans":
        return StartPayload(kind=PLANS)
    if raw == "inline_verify":
        return StartPayload(kind=INLINE_VERIFY)

    if raw.startswith("verify_"):
        token = raw[len("verify_"):]
        if token:
            return StartPayload(kind=VERIFY, token=token, resume=f"verify_{token}")
        return StartPayload(kind=UNKNOWN)

    if raw.startswith("all_"):
        parts = raw.split("_", 2)
        if len(parts) == 3 and _int(parts[1]) is not None and parts[2]:
            return StartPayload(kind=ALL, group_id=int(parts[1]), key=parts[2], resume=raw)
        return StartPayload(kind=UNKNOWN)

    for prefix, kind in (("file_", FILE), ("shortlink_", SHORTLINK)):
        if raw.startswith(prefix):
            parts = raw.split("_", 2)
            if len(parts) == 3 and _int(parts[1]) is not None and parts[2]:
                return StartPayload(
                    kind=kind, group_id=int(parts[1]), file_id=parts[2], resume=raw
                )
            return StartPayload(kind=UNKNOWN)

    return StartPayload(kind=UNKNOWN)


def parse_channel_link(text: str) -> tuple[int | str, int] | None:
    """``https://t.me/name/12`` / ``https://t.me/c/1234/12`` -> (chat, message id)."""
    match = PRIVATE_LINK.search(text or "")
    if match:
        return int(f"-100{match.group(1)}"), int(match.group(2))
    match = PUBLIC_LINK.search(text or "")
    if match:
        return match.group(1), int(match.group(2))
    return None


__all__ = [
    "ALL",
    "FILE",
    "HOME",
    "INLINE_VERIFY",
    "PLANS",
    "SHORTLINK",
    "StartPayload",
    "UNKNOWN",
    "VERIFY",
    "parse",
    "parse_channel_link",
]
