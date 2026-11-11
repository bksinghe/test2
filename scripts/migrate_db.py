#!/usr/bin/env python3
"""One-off migration from the legacy database schema to the new one.

The refactor keeps every collection name and every per-group setting key, so a
running deployment only needs three things converted:

===========================  ==========================================
legacy                       new
===========================  ==========================================
``Users.ban_status``         ``Users.banned``
``Users.verify_status``      ``Users.verify``
``uersz`` (premium, typo)    ``Users.premium_until`` / ``trial_used``
``Groups.chat_status``       ``Groups.disabled``
``Groups.<flat settings>``   ``Groups.settings.<key>``
``bot_id.bot_pm_search``     ``BotMeta.pm_search``
===========================  ==========================================

Usage::

    python scripts/migrate_db.py            # dry run, prints what would change
    python scripts/migrate_db.py --apply    # writes the changes

The script is idempotent: documents that are already in the new shape are
skipped, nothing is deleted, and the legacy collections stay untouched so you
can always roll back.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient

SETTING_KEYS = {
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
}

DATABASE_URL = os.environ.get("DATABASE_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.environ.get("DATABASE_NAME", "Cluster0")


def _datetime(value: Any) -> datetime | None:
    """Legacy code stored epoch seconds *and* naive datetimes, normalise both."""
    if value is None or value == 0:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=value.tzinfo or UTC)
    try:
        return datetime.fromtimestamp(float(value), tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


async def migrate_users(db, apply: bool) -> tuple[int, int]:
    migrated = skipped = 0
    async for doc in db.Users.find({}):
        if "banned" in doc and "verify" in doc:
            skipped += 1
            continue
        ban = doc.get("ban_status") or {}
        verify = doc.get("verify_status") or {}
        update: dict[str, Any] = {
            "banned": {
                "is_banned": bool(ban.get("is_banned")),
                "reason": ban.get("ban_reason") or "",
            },
            "verify": {
                "verified": bool(verify.get("is_verified")),
                "token": verify.get("verify_token") or "",
                "resume": verify.get("link") or "",
                "verified_at": _datetime(verify.get("verified_time")),
                "expires_at": _datetime(verify.get("expire_time")),
            },
            "premium_until": None,
            "trial_used": False,
        }
        if doc.get("name"):
            update["name"] = doc["name"]
        if "created_at" not in doc:
            update["created_at"] = datetime.now(UTC)
        migrated += 1
        if apply:
            await db.Users.update_one({"id": doc["id"]}, {"$set": update})
    return migrated, skipped


async def migrate_premium(db, apply: bool) -> int:
    """``uersz`` (sic) held premium state; merge it into the user documents."""
    migrated = 0
    collection = db["uersz"]
    async for doc in collection.find({}):
        user_id = doc.get("id")
        if user_id is None:
            continue
        until = _datetime(doc.get("expiry_time"))
        update: dict[str, Any] = {"trial_used": bool(doc.get("has_free_trial", False))}
        if until is not None:
            update["premium_until"] = until
        migrated += 1
        if apply:
            await db.Users.update_one(
                {"id": int(user_id)}, {"$set": update}, upsert=True
            )
    return migrated


async def migrate_chats(db, apply: bool) -> tuple[int, int]:
    migrated = skipped = 0
    async for doc in db.Groups.find({}):
        if "disabled" in doc and "settings" in doc:
            skipped += 1
            continue
        status = doc.get("chat_status") or {}
        settings = {key: doc[key] for key in SETTING_KEYS if key in doc and doc[key] != ""}
        update: dict[str, Any] = {
            "disabled": {
                "is_disabled": bool(status.get("is_disabled")),
                "reason": status.get("reason") or "",
            },
            "settings": settings,
        }
        if doc.get("title"):
            update["title"] = doc["title"]
        if "created_at" not in doc:
            update["created_at"] = datetime.now(UTC)
        migrated += 1
        if apply:
            await db.Groups.update_one({"id": doc["id"]}, {"$set": update})
    return migrated, skipped


async def migrate_pm_search(db, apply: bool) -> bool | None:
    doc = await db["bot_id"].find_one({})
    if not doc or "bot_pm_search" not in doc:
        return None
    value = bool(doc["bot_pm_search"])
    if apply:
        await db.BotMeta.update_one(
            {"_id": "pm_search"}, {"$set": {"value": value}}, upsert=True
        )
    return value


async def main(apply: bool) -> None:
    client = AsyncIOMotorClient(DATABASE_URL, tz_aware=True)
    db = client[DATABASE_NAME]
    mode = "APPLY" if apply else "DRY RUN (use --apply to write)"
    print(f"database={DATABASE_NAME} mode={mode}")

    users, users_skipped = await migrate_users(db, apply)
    premium = await migrate_premium(db, apply)
    chats, chats_skipped = await migrate_chats(db, apply)
    pm_search = await migrate_pm_search(db, apply)

    print(f"users migrated:      {users} (already new: {users_skipped})")
    print(f"premium rows merged: {premium}")
    print(f"groups migrated:     {chats} (already new: {chats_skipped})")
    print(f"pm search flag:      {pm_search if pm_search is not None else 'not found'}")
    if not apply:
        print("nothing was written")
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the changes")
    asyncio.run(main(parser.parse_args().apply))
