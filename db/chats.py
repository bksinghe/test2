"""Group repository: registration, enable/disable flags and per group settings."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from core.clock import utcnow
from db import mongo

NOT_DISABLED: dict[str, Any] = {"is_disabled": False, "reason": ""}


async def add(chat_id: int, title: str) -> bool:
    """Register a group. Returns ``True`` when it was not known before."""
    result = await mongo.chats.update_one(
        {"id": int(chat_id)},
        {
            "$set": {"title": title},
            "$setOnInsert": {"disabled": dict(NOT_DISABLED), "settings": {}, "created_at": utcnow()},
        },
        upsert=True,
    )
    return result.upserted_id is not None


async def exists(chat_id: int) -> bool:
    return await mongo.chats.count_documents({"id": int(chat_id)}, limit=1) > 0


async def get(chat_id: int) -> dict[str, Any] | None:
    return await mongo.chats.find_one({"id": int(chat_id)})


async def status(chat_id: int) -> dict[str, Any]:
    doc = await mongo.chats.find_one({"id": int(chat_id)}, {"disabled": 1})
    if not doc:
        return dict(NOT_DISABLED)
    return {**NOT_DISABLED, **(doc.get("disabled") or {})}


async def set_disabled(chat_id: int, disabled: bool, reason: str = "") -> None:
    await mongo.chats.update_one(
        {"id": int(chat_id)},
        {"$set": {"disabled": {"is_disabled": disabled, "reason": reason}}},
        upsert=True,
    )


async def disabled_ids() -> list[int]:
    return [doc["id"] async for doc in mongo.chats.find({"disabled.is_disabled": True}, {"id": 1})]


async def count() -> int:
    return await mongo.chats.count_documents({})


def all_chats() -> AsyncIterator[dict[str, Any]]:
    return mongo.chats.find({}, {"id": 1, "title": 1, "disabled": 1}).sort("id", 1)


async def delete(chat_id: int) -> None:
    await mongo.chats.delete_one({"id": int(chat_id)})


# ---------------------------------------------------------------- settings
async def stored_settings(chat_id: int) -> dict[str, Any]:
    doc = await mongo.chats.find_one({"id": int(chat_id)}, {"settings": 1})
    return (doc or {}).get("settings") or {}


async def save_settings(chat_id: int, values: dict[str, Any]) -> None:
    await mongo.chats.update_one(
        {"id": int(chat_id)}, {"$set": {"settings": values}}, upsert=True
    )


async def save_setting(chat_id: int, key: str, value: Any) -> None:
    await mongo.chats.update_one(
        {"id": int(chat_id)}, {"$set": {f"settings.{key}": value}}, upsert=True
    )


__all__ = [
    "NOT_DISABLED",
    "add",
    "all_chats",
    "count",
    "delete",
    "disabled_ids",
    "exists",
    "get",
    "save_setting",
    "save_settings",
    "set_disabled",
    "status",
    "stored_settings",
]
