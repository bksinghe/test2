"""Single MongoDB connection shared by every repository.

The legacy bot created users and chats with a ``find_one`` + ``insert``
sandwich, so old databases contain documents with the same ``id`` more than
once. A unique index cannot be built on such a collection, and the old code
died at startup with ``E11000 duplicate key``. Index creation here is
therefore defensive: duplicates are merged first, and if a unique index still
cannot be built the bot logs it and keeps running instead of exiting.
"""

from __future__ import annotations

import logging
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError, OperationFailure

from config import settings

log = logging.getLogger(__name__)

FALLBACK_URI = "mongodb://localhost:27017"

client: AsyncIOMotorClient = AsyncIOMotorClient(
    settings.database_url or FALLBACK_URI,
    tz_aware=True,
    # fail fast instead of motor's 30s default when the URI is wrong
    serverSelectionTimeoutMS=10000,
    connectTimeoutMS=10000,
)
db = client[settings.database_name]

media = db[settings.media_collection]
users = db[settings.users_collection]
chats = db[settings.chats_collection]
meta = db[settings.meta_collection]
streams = db[settings.stream_collection]

#: values that hold no information when merging duplicate documents
EMPTY = (None, "", {}, [])


async def ping() -> bool:
    try:
        await client.admin.command("ping")
        return True
    except Exception:  # noqa: BLE001 - motor raises many different errors
        return False


# --------------------------------------------------------------- merging
def _is_empty(value: Any) -> bool:
    return value in EMPTY or value is None


def _richest(docs: list[dict[str, Any]]) -> dict[str, Any]:
    """The document that carries the most information wins."""
    return max(docs, key=lambda doc: sum(1 for value in doc.values() if not _is_empty(value)))


def merge_user_docs(docs: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge duplicate user rows: bans, verification and premium are unioned."""
    merged = dict(_richest(docs))
    banned = next(
        (doc["banned"] for doc in docs if (doc.get("banned") or {}).get("is_banned")), None
    )
    if banned:
        merged["banned"] = banned

    verified = [
        doc["verify"] for doc in docs if (doc.get("verify") or {}).get("verified")
    ]
    if verified:
        merged["verify"] = max(
            verified, key=lambda verify: str(verify.get("verified_at") or "")
        )

    premium = [doc.get("premium_until") for doc in docs if doc.get("premium_until")]
    if premium:
        merged["premium_until"] = max(premium)
    merged["trial_used"] = any(doc.get("trial_used") for doc in docs)

    created = [doc.get("created_at") for doc in docs if doc.get("created_at")]
    if created:
        merged["created_at"] = min(created)
    return merged


def merge_chat_docs(docs: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge duplicate chat rows: a disabled flag and the settings are kept."""
    merged = dict(_richest(docs))
    disabled = next(
        (doc["disabled"] for doc in docs if (doc.get("disabled") or {}).get("is_disabled")), None
    )
    if disabled:
        merged["disabled"] = disabled

    # collect every value per key, then let the "on"/non empty one win: a
    # setting that somebody enabled must not be lost to a default ``False``
    options: dict[str, list[Any]] = {}
    for doc in docs:
        for key, value in (doc.get("settings") or {}).items():
            options.setdefault(key, []).append(value)
    if options:
        merged["settings"] = {
            key: next((value for value in values if value), values[0])
            for key, values in options.items()
        }

    created = [doc.get("created_at") for doc in docs if doc.get("created_at")]
    if created:
        merged["created_at"] = min(created)
    return merged


MERGE = {
    settings.users_collection: merge_user_docs,
    settings.chats_collection: merge_chat_docs,
}


async def dedupe(collection, field: str = "id") -> int:
    """Merge documents that share ``field``; returns how many rows were removed."""
    merge = MERGE.get(collection.name, lambda docs: _richest(docs))
    removed = 0
    pipeline = [
        {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
    ]
    async for group in collection.aggregate(pipeline, allowDiskUse=True):
        docs = [doc async for doc in collection.find({field: group["_id"]})]
        if len(docs) < 2:
            continue
        merged = merge(docs)
        keep_id = merged["_id"]
        dropped = [doc["_id"] for doc in docs if doc["_id"] != keep_id]
        await collection.replace_one({"_id": keep_id}, merged, upsert=True)
        await collection.delete_many({"_id": {"$in": dropped}})
        removed += len(dropped)
        log.info(
            "%s: merged %s duplicate documents for %s=%r",
            collection.name,
            len(dropped),
            field,
            group["_id"],
        )
    return removed


# --------------------------------------------------------------- indexes
async def _create(collection, keys, *, unique: bool = False) -> bool:
    try:
        await collection.create_index(keys, unique=unique)
        return True
    except (DuplicateKeyError, OperationFailure) as error:
        log.warning("index %s%s could not be created: %s", collection.name, keys, error)
        return False


async def _unique(collection, field: str) -> None:
    try:
        info = await collection.index_information()
    except Exception:  # noqa: BLE001 - permission problems must not stop the bot
        info = {}
    if info.get(f"{field}_1", {}).get("unique"):
        return  # already there, nothing to rebuild on every start
    if await _create(collection, field, unique=True):
        return
    removed = await dedupe(collection, field)
    if await _create(collection, field, unique=True):
        if removed:
            log.warning("%s: removed %s duplicate rows to build the unique index", collection.name, removed)
    else:
        log.error(
            "%s.%s still has duplicates - the unique index is missing, "
            "run scripts/migrate_db.py --apply to clean it",
            collection.name,
            field,
        )


async def ensure_indexes() -> None:
    await _unique(users, "id")
    await _unique(chats, "id")
    await _create(media, "file_name")
    await _unique(streams, "file_id")


async def close() -> None:
    client.close()


__all__ = [
    "chats",
    "client",
    "close",
    "db",
    "dedupe",
    "ensure_indexes",
    "media",
    "merge_chat_docs",
    "merge_user_docs",
    "meta",
    "ping",
    "streams",
    "users",
]
