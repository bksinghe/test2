"""Premium subscriptions and the one time free trial."""

from __future__ import annotations

from datetime import datetime, timedelta

from core.cache import TTLCache
from core.clock import as_utc, utcnow
from db import users

FREE_TRIAL = timedelta(minutes=5)

# expiry checks happen on almost every message; 30s of caching is plenty and
# grants/revokes invalidate it explicitly.
_cache: TTLCache = TTLCache(ttl=30, maxsize=10000)


async def has_premium(user_id: int | None) -> bool:
    if not user_id:
        return False
    cached = _cache.get(user_id)
    if cached is not None:
        return bool(cached)
    until = await users.premium_until(int(user_id))
    active = bool(until and until > utcnow())
    _cache.set(user_id, active)
    return active


def invalidate(user_id: int) -> None:
    _cache.pop(int(user_id))


async def remaining(user_id: int) -> timedelta | None:
    until = await users.premium_until(int(user_id))
    if not until or until <= utcnow():
        return None
    return until - utcnow()


async def expires_at(user_id: int) -> datetime | None:
    return as_utc(await users.premium_until(int(user_id)))


async def grant(user_id: int, seconds: int) -> datetime:
    start = utcnow()
    current = await users.premium_until(int(user_id))
    if current and current > start:
        start = current
    until = start + timedelta(seconds=max(1, seconds))
    await users.set_premium(int(user_id), until)
    invalidate(user_id)
    return until


async def revoke(user_id: int) -> None:
    await users.set_premium(int(user_id), utcnow() - timedelta(seconds=1))
    invalidate(user_id)


async def trial_available(user_id: int) -> bool:
    return not await users.trial_used(int(user_id))


async def start_trial(user_id: int) -> bool:
    if await users.trial_used(int(user_id)):
        return False
    await users.mark_trial(int(user_id))
    await grant(int(user_id), int(FREE_TRIAL.total_seconds()))
    return True


__all__ = [
    "FREE_TRIAL",
    "expires_at",
    "grant",
    "has_premium",
    "invalidate",
    "remaining",
    "revoke",
    "start_trial",
    "trial_available",
]
