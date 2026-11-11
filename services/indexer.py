"""Indexing media from channels into the searchable database."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pyrogram import Client
from pyrogram.types import Message

from core import state
from db import media
from services.file_ids import normalize

log = logging.getLogger(__name__)

MEDIA_KINDS = ("video", "document", "audio")
PROGRESS_STEP = 30


@dataclass(slots=True)
class IndexStats:
    current: int = 0
    saved: int = 0
    duplicates: int = 0
    deleted: int = 0
    skipped: int = 0
    errors: int = 0


def extract_media(message: Message) -> Any | None:
    for kind in MEDIA_KINDS:
        media_object = getattr(message, kind, None)
        if media_object is not None:
            return media_object
    return None


def _file_name(media_object: Any) -> str | None:
    return (
        getattr(media_object, "file_name", None)
        or getattr(media_object, "title", None)
        or None
    )


async def save_message(message: Message) -> str:
    """Save a single media message. Returns ``saved``/``duplicate``/``invalid``."""
    media_object = extract_media(message)
    if media_object is None:
        return "invalid"
    try:
        file_id = normalize(media_object.file_id)
    except Exception as error:  # noqa: BLE001 - unsupported/odd file ids
        log.debug("could not normalise file id: %s", error)
        file_id = media_object.file_id
    return await media.save(
        file_id=file_id,
        file_name=_file_name(media_object),
        file_size=getattr(media_object, "file_size", 0) or 0,
        caption=message.caption,
    )


async def iter_messages(
    client: Client, chat_id: int | str, limit: int, offset: int = 0
) -> AsyncGenerator[Message, None]:
    """Yield messages sequentially without exhausting the API rate limit."""
    current = max(0, offset)
    while current < limit:
        chunk = min(200, limit - current)
        if chunk <= 0:
            return
        messages = await client.get_messages(chat_id, list(range(current, current + chunk)))
        for message in messages:
            current += 1
            yield message


Progress = Callable[[IndexStats], Awaitable[None]]


async def index_range(
    client: Client,
    *,
    chat_id: int | str,
    last_message_id: int,
    skip: int = 0,
    progress: Progress | None = None,
) -> IndexStats:
    """Index messages ``skip..last_message_id`` of ``chat_id``."""
    stats = IndexStats(current=skip)
    state.index_cancel = False

    async for message in iter_messages(client, chat_id, last_message_id, skip):
        if state.index_cancel:
            break
        stats.current += 1

        if progress and stats.current % PROGRESS_STEP == 0:
            try:
                await progress(stats)
            except Exception as error:  # noqa: BLE001 - progress is cosmetic
                log.debug("progress update failed: %s", error)

        if message is None or getattr(message, "empty", False):
            stats.deleted += 1
            continue
        if not message.media:
            stats.skipped += 1
            continue

        status = await save_message(message)
        if status == "saved":
            stats.saved += 1
        elif status == "duplicate":
            stats.duplicates += 1
        else:
            stats.skipped += 1

    state.index_cancel = False
    return stats


__all__ = ["IndexStats", "extract_media", "index_range", "iter_messages", "save_message"]
