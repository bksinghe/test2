"""Legacy schema migration, run automatically on startup.

The old bot stored users and chats differently, and an existing deployment
would otherwise silently lose bans, verification, premium and per group
settings after the upgrade (the new code looks for ``banned``/``verify`` while
the old documents have ``ban_status``/``verify_status``).

Everything here is **idempotent** and only touches documents that still look
legacy, so it is safe to run on every start:

===============  =========================================
legacy                        new
===============  =========================================
``Users.ban_status``          ``Users.banned``
``Users.verify_status``       ``Users.verify``
``uersz`` (premium, typo)     ``Users.premium_until`` / ``trial_used``
``Groups.chat_status``        ``Groups.disabled``
``Groups.<flat settings>``    ``Groups.settings.<key>``
``bot_id.bot_pm_search``      ``BotMeta.pm_search``
===============  =========================================

User documents are converted with a single server side aggregation update
(cheap even for large collections); groups and the tiny premium collection are
converted in python because their documents need per field merging.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from core.clock import as_utc, utcnow
from db import mongo

log = logging.getLogger(__name__)

#: the only per group settings the bot knows about (same keys as the legacy bot)
SETTING_KEYS = (
    "auto_filter",
    "file_secure",
    "imdb",
    "spell_check",
    "auto_delete",
    "welcome",
    "welcome_text",
    "template",
    "caption",
    "url",
    "api",
    "shortlink",
    "tutorial",
    "links",
    "fsub",
    "is_stream",
)

#: set once the (never modified) legacy premium collection has been merged
PREMIUM_FLAG = "legacy_premium_migrated"

LEGACY_USERS = {
    "$or": [
        {"ban_status": {"$exists": True}},
        {"verify_status": {"$exists": True}},
        {"banned": {"$exists": False}},
        {"verify": {"$exists": False}},
        {"id": {"$type": "string"}},
    ]
}

LEGACY_GROUPS = {
    "$or": [
        {"chat_status": {"$exists": True}},
        {"settings": {"$exists": False}},
        {"disabled": {"$exists": False}},
        {"id": {"$type": "string"}},
    ]
}


def _timestamp(path: str) -> dict[str, Any]:
    """Accept both epoch seconds (legacy) and real datetimes."""
    return {
        "$switch": {
            "branches": [
                {"case": {"$eq": [{"$type": path}, "date"]}, "then": path},
                {
                    "case": {"$gt": [{"$ifNull": [path, 0]}, 0]},
                    "then": {"$toDate": {"$multiply": [path, 1000]}},
                },
            ],
            "default": None,
        }
    }


def _preferred(path: str, legacy: dict[str, Any]) -> dict[str, Any]:
    """Keep an already migrated value, otherwise build it from the old field."""
    return {"$cond": [{"$eq": [{"$ifNull": [path, None]}, None]}, legacy, path]}


USER_PIPELINE = [
    {
        "$set": {
            "id": {
                "$convert": {
                    "input": "$id",
                    "to": "long",
                    "onError": "$id",
                    "onNull": "$id",
                }
            },
            "banned": _preferred(
                "$banned",
                {
                    "is_banned": {"$ifNull": ["$ban_status.is_banned", False]},
                    "reason": {"$ifNull": ["$ban_status.ban_reason", ""]},
                },
            ),
            "verify": _preferred(
                "$verify",
                {
                    "verified": {"$ifNull": ["$verify_status.is_verified", False]},
                    "token": {"$ifNull": ["$verify_status.verify_token", ""]},
                    "resume": {"$ifNull": ["$verify_status.link", ""]},
                    "verified_at": _timestamp("$verify_status.verified_time"),
                    "expires_at": _timestamp("$verify_status.expire_time"),
                },
            ),
            "premium_until": {"$ifNull": ["$premium_until", None]},
            "trial_used": {"$ifNull": ["$trial_used", False]},
            "created_at": {"$ifNull": ["$created_at", "$$NOW"]},
        }
    },
    {"$unset": ["ban_status", "verify_status"]},
]


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_datetime(value: Any) -> datetime | None:
    if value is None or value == 0:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    number = _as_int(value)
    if number is None:
        return None
    try:
        return datetime.fromtimestamp(number, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


async def migrate_users() -> int:
    """Convert bans/verification and coerce ``id`` to int in one command."""
    try:
        result = await mongo.users.update_many(LEGACY_USERS, USER_PIPELINE)
        return result.modified_count
    except Exception as error:  # noqa: BLE001 - old mongod without pipeline updates
        log.warning("aggregation migration failed (%s), converting row by row", error)
        return await _migrate_users_row_by_row()


async def _migrate_users_row_by_row() -> int:
    """Fallback for servers that reject update pipelines (pre 4.2)."""
    changed = 0
    async for doc in mongo.users.find(LEGACY_USERS):
        update: dict[str, Any] = {}
        if not isinstance(doc.get("banned"), dict):
            ban = doc.get("ban_status") or {}
            update["banned"] = {
                "is_banned": bool(ban.get("is_banned")),
                "reason": ban.get("ban_reason") or "",
            }
        if not isinstance(doc.get("verify"), dict):
            verify = doc.get("verify_status") or {}
            update["verify"] = {
                "verified": bool(verify.get("is_verified")),
                "token": verify.get("verify_token") or "",
                "resume": verify.get("link") or "",
                "verified_at": _as_datetime(verify.get("verified_time")),
                "expires_at": _as_datetime(verify.get("expire_time")),
            }
        if "premium_until" not in doc:
            update["premium_until"] = None
        if "trial_used" not in doc:
            update["trial_used"] = False
        if not doc.get("created_at"):
            update["created_at"] = utcnow()

        user_id = _as_int(doc.get("id"))
        if user_id is not None and user_id != doc.get("id"):
            update["id"] = user_id

        if not update:
            continue
        update_doc: dict[str, Any] = {"$set": update, "$unset": {"ban_status": "", "verify_status": ""}}
        await mongo.users.update_one({"_id": doc["_id"]}, update_doc)
        changed += 1
    return changed


async def migrate_groups() -> int:
    changed = 0
    async for doc in mongo.chats.find(LEGACY_GROUPS):
        update: dict[str, Any] = {}
        unset: dict[str, str] = {}

        chat_id = doc.get("id")
        if isinstance(chat_id, str) and chat_id.lstrip("-").isdigit():
            update["id"] = int(chat_id)

        if "disabled" not in doc:
            status = doc.get("chat_status") or {}
            update["disabled"] = {
                "is_disabled": bool(status.get("is_disabled")),
                "reason": status.get("reason") or "",
            }
            if "chat_status" in doc:
                unset["chat_status"] = ""

        if "settings" not in doc:
            update["settings"] = {
                key: doc[key] for key in SETTING_KEYS if not _blank(doc.get(key))
            }
            # the flat copies are what confused the old code; drop them
            for key in SETTING_KEYS:
                if key in doc:
                    unset[key] = ""

        if not doc.get("created_at"):
            update["created_at"] = utcnow()

        if not update and not unset:
            continue

        update_doc: dict[str, Any] = {"$set": update}
        if unset:
            update_doc["$unset"] = unset
        await mongo.chats.update_one({"_id": doc["_id"]}, update_doc)
        changed += 1
    return changed


async def migrate_premium() -> int:
    """The premium data lived in a typo'd ``uersz`` collection."""
    if await mongo.meta.find_one({"_id": PREMIUM_FLAG}):
        return 0
    changed = 0
    async for doc in mongo.db["uersz"].find({}):
        user_id = _as_int(doc.get("id"))
        if user_id is None:
            continue
        update: dict[str, Any] = {"trial_used": bool(doc.get("has_free_trial", False))}
        until = _as_datetime(doc.get("expiry_time"))
        if until is not None:
            update["premium_until"] = as_utc(until)
        await mongo.users.update_one({"id": user_id}, {"$set": update}, upsert=True)
        changed += 1
    await mongo.meta.update_one(
        {"_id": PREMIUM_FLAG}, {"$set": {"value": True}}, upsert=True
    )
    return changed


async def migrate_pm_search() -> int:
    """``bot_id.bot_pm_search`` becomes a bot wide flag."""
    doc = await mongo.db["bot_id"].find_one({})
    if not doc or "bot_pm_search" not in doc:
        return 0
    value = bool(doc["bot_pm_search"])
    current = await mongo.meta.find_one({"_id": "pm_search"})
    if current is not None and bool(current.get("value")) == value:
        return 0
    await mongo.meta.update_one({"_id": "pm_search"}, {"$set": {"value": value}}, upsert=True)
    return 1


def _blank(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


async def run() -> dict[str, int]:
    """Run every migration; returns the number of documents touched per step."""
    report = {
        "users": await migrate_users(),
        "groups": await migrate_groups(),
        "premium": await migrate_premium(),
        "pm_search": await migrate_pm_search(),
    }
    touched = {key: value for key, value in report.items() if value}
    if touched:
        log.info("legacy documents migrated: %s", touched)
    return report


async def pending_counts() -> dict[str, int]:
    """How many documents still need a migration (used by the CLI dry run)."""
    duplicates = 0
    for collection in (mongo.users, mongo.chats):
        pipeline = [
            {"$group": {"_id": "$id", "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 1}}},
            {"$group": {"_id": None, "rows": {"$sum": {"$subtract": ["$count", 1]}}}},
        ]
        async for row in collection.aggregate(pipeline, allowDiskUse=True):
            duplicates += int(row["rows"])
    return {
        "users": await mongo.users.count_documents(LEGACY_USERS),
        "groups": await mongo.chats.count_documents(LEGACY_GROUPS),
        "premium": await mongo.db["uersz"].count_documents({}),
        "duplicates": duplicates,
    }


__all__ = [
    "LEGACY_GROUPS",
    "PREMIUM_FLAG",
    "LEGACY_USERS",
    "SETTING_KEYS",
    "USER_PIPELINE",
    "migrate_groups",
    "migrate_pm_search",
    "migrate_premium",
    "migrate_users",
    "pending_counts",
    "run",
]
