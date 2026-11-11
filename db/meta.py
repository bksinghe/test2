"""Small key/value store for bot wide flags and the stream message cache."""

from __future__ import annotations

from db import mongo

PM_SEARCH_ID = "pm_search"


async def pm_search_enabled(default: bool = True) -> bool:
    doc = await mongo.meta.find_one({"_id": PM_SEARCH_ID})
    if doc is None:
        return default
    return bool(doc.get("value", default))


async def set_pm_search(enabled: bool) -> None:
    await mongo.meta.update_one(
        {"_id": PM_SEARCH_ID}, {"$set": {"value": bool(enabled)}}, upsert=True
    )


async def cached_stream_message(file_id: str) -> int | None:
    doc = await mongo.streams.find_one({"file_id": file_id})
    return int(doc["message_id"]) if doc else None


async def cache_stream_message(file_id: str, message_id: int) -> None:
    await mongo.streams.update_one(
        {"file_id": file_id}, {"$set": {"message_id": int(message_id)}}, upsert=True
    )


async def forget_stream_message(file_id: str) -> None:
    await mongo.streams.delete_one({"file_id": file_id})


__all__ = [
    "cache_stream_message",
    "cached_stream_message",
    "forget_stream_message",
    "pm_search_enabled",
    "set_pm_search",
]
