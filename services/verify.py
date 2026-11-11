"""Shortlink based verification.

Expiry handling is defensive: a missing/legacy ``expires_at`` never raises and
an expired verification simply means "verify again".
"""

from __future__ import annotations

import secrets
import string
from typing import Any

from config import settings
from core.cache import TTLCache
from core.clock import as_utc, utcnow
from db import users
from services import premium, shortlink

ALPHABET = string.ascii_letters + string.digits
_cache: TTLCache = TTLCache(ttl=60, maxsize=10000)


def new_token(length: int = 10) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def _is_valid(record: dict[str, Any]) -> bool:
    if not record.get("verified"):
        return False
    expires = as_utc(record.get("expires_at"))
    return bool(expires and expires > utcnow())


async def is_verified(user_id: int) -> bool:
    cached = _cache.get(user_id)
    if cached is not None:
        return bool(cached)
    record = await users.verify(int(user_id))
    valid = _is_valid(record)
    _cache.set(user_id, valid)
    return valid


def invalidate(user_id: int) -> None:
    _cache.pop(int(user_id))


async def reset(user_id: int) -> None:
    await users.set_verify(int(user_id), verified=False, token="", resume="")
    invalidate(user_id)


async def needs_verification(user_id: int) -> bool:
    if not settings.verify:
        return False
    if await premium.has_premium(user_id):
        return False
    return not await is_verified(user_id)


async def begin(user_id: int, resume: str) -> tuple[str, str]:
    """Create a token and return ``(token, verify_url)``.

    The URL is shortlink wrapped when a shortener is configured; otherwise the
    direct Telegram link is returned so verification keeps working.
    """
    token = new_token()
    await users.set_verify(int(user_id), verified=False, token=token, resume=resume or "")
    invalidate(user_id)

    direct = f"https://t.me/{_bot_username()}?start=verify_{token}"
    url = direct
    if settings.shortlink_url and settings.shortlink_api:
        wrapped = await shortlink.shorten(settings.shortlink_url, settings.shortlink_api, direct)
        if wrapped:
            url = wrapped
    return token, url


async def confirm(user_id: int, token: str) -> str | None:
    """Validate ``token`` and mark the user verified.

    Returns the resume payload ("" when there was none) or ``None`` when the
    token is invalid.
    """
    record = await users.verify(int(user_id))
    if not record.get("token") or record.get("token") != token:
        return None
    await users.set_verify(
        int(user_id),
        verified=True,
        token="",
        verified_at=utcnow(),
        expires_at=utcnow() + _expiry(),
    )
    invalidate(user_id)
    return record.get("resume") or ""


def _expiry():
    from datetime import timedelta

    return timedelta(seconds=max(60, settings.verify_expire))


def _bot_username() -> str:
    from core import state

    return state.username or "bot"


__all__ = [
    "begin",
    "confirm",
    "invalidate",
    "is_verified",
    "needs_verification",
    "new_token",
    "reset",
]
