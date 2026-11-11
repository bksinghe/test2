"""Single MongoDB connection shared by every repository."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient

from config import settings

FALLBACK_URI = "mongodb://localhost:27017"

client: AsyncIOMotorClient = AsyncIOMotorClient(
    settings.database_url or FALLBACK_URI, tz_aware=True
)
db = client[settings.database_name]

media = db[settings.media_collection]
users = db[settings.users_collection]
chats = db[settings.chats_collection]
meta = db[settings.meta_collection]
streams = db[settings.stream_collection]


async def ping() -> bool:
    try:
        await client.admin.command("ping")
        return True
    except Exception:  # noqa: BLE001 - motor raises many different errors
        return False


async def ensure_indexes() -> None:
    await users.create_index("id", unique=True)
    await chats.create_index("id", unique=True)
    await media.create_index("file_name")
    await streams.create_index("file_id", unique=True)
    await meta.create_index("_id", unique=True)


async def close() -> None:
    client.close()


__all__ = ["chats", "client", "close", "db", "ensure_indexes", "media", "meta", "ping", "streams", "users"]
