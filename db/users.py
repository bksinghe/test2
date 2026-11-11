"""User repository: identity, bans, verification and premium in one document.

The old code split users over two collections (``Users`` for bans/verification
and a typo'd ``uersz`` for premium), which made state inconsistent. Everything
now lives in a single document:

    {id, name, created_at,
     banned: {is_banned, reason},
     verify: {verified, token, resume, verified_at, expires_at},
     premium_until: datetime | None,
     trial_used: bool}
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from core.clock import as_utc, utcnow
from db import mongo

DEFAULT_VERIFY: dict[str, Any] = {
    "verified": False,
    "token": "",
    "resume": "",
    "verified_at": None,
    "expires_at": None,
}

NOT_BANNED: dict[str, Any] = {"is_banned": False, "reason": ""}


def _new_verify() -> dict[str, Any]:
    return dict(DEFAULT_VERIFY)


async def add(user_id: int, name: str) -> bool:
    """Insert a user if needed. Returns ``True`` when the user is new."""
    result = await mongo.users.update_one(
        {"id": int(user_id)},
        {
            "$set": {"name": name},
            "$setOnInsert": {
                "banned": dict(NOT_BANNED),
                "verify": _new_verify(),
                "premium_until": None,
                "trial_used": False,
                "created_at": utcnow(),
            },
        },
        upsert=True,
    )
    return result.upserted_id is not None


async def exists(user_id: int) -> bool:
    return await mongo.users.count_documents({"id": int(user_id)}, limit=1) > 0


async def get(user_id: int) -> dict[str, Any] | None:
    return await mongo.users.find_one({"id": int(user_id)})


async def count() -> int:
    return await mongo.users.count_documents({})


def all_users() -> AsyncIterator[dict[str, Any]]:
    return mongo.users.find({}, {"id": 1, "name": 1, "banned": 1, "verify": 1}).sort("id", 1)


async def delete(user_id: int) -> None:
    await mongo.users.delete_one({"id": int(user_id)})


# ------------------------------------------------------------------- ban
async def set_ban(user_id: int, reason: str = "No reason provided") -> None:
    await mongo.users.update_one(
        {"id": int(user_id)},
        {"$set": {"banned": {"is_banned": True, "reason": reason}}},
        upsert=True,
    )


async def clear_ban(user_id: int) -> None:
    await mongo.users.update_one(
        {"id": int(user_id)}, {"$set": {"banned": dict(NOT_BANNED)}}, upsert=True
    )


async def ban_status(user_id: int) -> dict[str, Any]:
    doc = await mongo.users.find_one({"id": int(user_id)}, {"banned": 1})
    if not doc:
        return dict(NOT_BANNED)
    return {**NOT_BANNED, **(doc.get("banned") or {})}


async def banned_ids() -> list[int]:
    return [doc["id"] async for doc in mongo.users.find({"banned.is_banned": True}, {"id": 1})]


# ---------------------------------------------------------------- verify
async def verify(user_id: int) -> dict[str, Any]:
    doc = await mongo.users.find_one({"id": int(user_id)}, {"verify": 1})
    stored = (doc or {}).get("verify") or {}
    return {**_new_verify(), **stored}


async def set_verify(user_id: int, **fields: Any) -> None:
    await mongo.users.update_one(
        {"id": int(user_id)},
        {"$set": {f"verify.{key}": value for key, value in fields.items()}},
        upsert=True,
    )


# --------------------------------------------------------------- premium
async def premium_until(user_id: int) -> datetime | None:
    doc = await mongo.users.find_one({"id": int(user_id)}, {"premium_until": 1})
    return as_utc((doc or {}).get("premium_until"))


async def set_premium(user_id: int, until: datetime | None) -> None:
    await mongo.users.update_one(
        {"id": int(user_id)}, {"$set": {"premium_until": as_utc(until)}}, upsert=True
    )


async def premium_count() -> int:
    return await mongo.users.count_documents({"premium_until": {"$gt": utcnow()}})


async def trial_used(user_id: int) -> bool:
    doc = await mongo.users.find_one({"id": int(user_id)}, {"trial_used": 1})
    return bool((doc or {}).get("trial_used"))


async def mark_trial(user_id: int) -> None:
    await mongo.users.update_one({"id": int(user_id)}, {"$set": {"trial_used": True}}, upsert=True)


__all__ = [
    "DEFAULT_VERIFY",
    "add",
    "all_users",
    "ban_status",
    "banned_ids",
    "clear_ban",
    "count",
    "delete",
    "exists",
    "get",
    "mark_trial",
    "premium_count",
    "premium_until",
    "set_ban",
    "set_premium",
    "set_verify",
    "trial_used",
    "verify",
]
