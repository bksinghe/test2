"""Sending indexed files to users, with optional auto deletion."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pyrogram import Client
from pyrogram.errors import MessageNotModified
from pyrogram.types import InlineKeyboardMarkup, Message

from config import settings
from core import state
from core.fmt import human_size, readable_time
from db.media import MediaFile
from services import premium
from ui import keyboards as kb
from ui import texts

log = logging.getLogger(__name__)

def caption_for(chat_settings: dict[str, Any], file: MediaFile) -> str:
    template = chat_settings.get("caption") or settings.file_caption
    size = human_size(file.file_size)
    context = {
        "file_name": file.file_name,
        "file_size": size,
        "size": size,
        "file_caption": file.caption,
        "caption": file.caption,
    }
    try:
        return template.format(**context)
    except (KeyError, IndexError, ValueError):
        log.warning("invalid file caption template: %r", template)
        return f"<b>{file.file_name}</b>\n<b>{size}</b>"


def _protect(chat_settings: dict[str, Any], is_premium: bool) -> bool:
    """``file_secure`` used to be stored but ignored; it is honoured now."""
    return bool(chat_settings.get("file_secure")) and not is_premium


async def send_file(
    client: Client,
    *,
    chat_id: int,
    file: MediaFile,
    chat_settings: dict[str, Any],
    is_premium: bool,
    stream: bool,
) -> Message:
    return await client.send_cached_media(
        chat_id=chat_id,
        file_id=file.file_id,
        caption=caption_for(chat_settings, file),
        protect_content=_protect(chat_settings, is_premium),
        reply_markup=kb.file_keyboard(file.file_id, stream),
    )


async def deliver_single(
    client: Client,
    *,
    chat_id: int,
    group_id: int,
    file: MediaFile,
    chat_settings: dict[str, Any],
) -> Message:
    is_premium = await premium.has_premium(chat_id)
    message = await send_file(
        client,
        chat_id=chat_id,
        file=file,
        chat_settings=chat_settings,
        is_premium=is_premium,
        stream=bool(chat_settings.get("is_stream")),
    )
    note = await client.send_message(
        chat_id=chat_id,
        text=texts.PM_FILES_NOTICE.format(delay=readable_time(settings.pm_delete_time)),
    )
    state.spawn(
        _delete_later(
            client,
            chat_id=chat_id,
            message_ids=[message.id, note.id],
            note_id=note.id,
            keyboard=kb.regain_keyboard("file", group_id, file.file_id),
        )
    )
    return message


async def deliver_all(
    client: Client,
    *,
    chat_id: int,
    group_id: int,
    files: list[MediaFile],
    chat_settings: dict[str, Any],
    token: str,
) -> None:
    if not files:
        await client.send_message(chat_id=chat_id, text=texts.INVALID_LINK)
        return

    is_premium = await premium.has_premium(chat_id)
    counter = await client.send_message(
        chat_id=chat_id, text=f"<b><i>🗂 Total files - <code>{len(files)}</code></i></b>"
    )
    sent: list[int] = []
    for file in files:
        try:
            message = await send_file(
                client,
                chat_id=chat_id,
                file=file,
                chat_settings=chat_settings,
                is_premium=is_premium,
                stream=bool(chat_settings.get("is_stream")),
            )
            sent.append(message.id)
        except Exception as error:  # noqa: BLE001 - keep sending the rest
            log.warning("could not deliver %s: %s", file.file_name, error)

    note = await client.send_message(
        chat_id=chat_id,
        text=texts.PM_FILES_NOTICE.format(delay=readable_time(settings.pm_delete_time)),
    )
    state.spawn(
        _delete_later(
            client,
            chat_id=chat_id,
            message_ids=sent + [counter.id, note.id],
            note_id=note.id,
            keyboard=kb.regain_keyboard("all", group_id, token),
        )
    )


async def _delete_later(
    client: Client,
    *,
    chat_id: int,
    message_ids: list[int],
    note_id: int,
    keyboard: InlineKeyboardMarkup,
) -> None:
    try:
        await asyncio.sleep(settings.pm_delete_time)
        await client.delete_messages(chat_id=chat_id, message_ids=message_ids)
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=note_id,
            text=texts.FILES_GONE,
            reply_markup=keyboard,
        )
    except asyncio.CancelledError:
        raise
    except MessageNotModified:
        pass
    except Exception as error:  # noqa: BLE001 - deletions are best effort
        log.debug("auto delete failed in %s: %s", chat_id, error)


def schedule_group_delete(
    client: Client,
    *,
    chat_id: int,
    message_id: int,
    source_message_id: int | None = None,
) -> None:
    """Delete a group result (and the request) after ``DELETE_TIME``."""

    async def _task() -> None:
        try:
            await asyncio.sleep(settings.delete_time)
            await client.delete_messages(chat_id=chat_id, message_ids=message_id)
            if source_message_id:
                await client.delete_messages(chat_id=chat_id, message_ids=source_message_id)
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001
            log.debug("group auto delete failed in %s: %s", chat_id, error)

    state.spawn(_task())


def schedule_cleanup(client: Client, *, chat_id: int, message_ids: list[int], delay: int = 60) -> None:
    async def _task() -> None:
        try:
            await asyncio.sleep(delay)
            await client.delete_messages(chat_id=chat_id, message_ids=message_ids)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            pass

    state.spawn(_task())


__all__ = [
    "caption_for",
    "deliver_all",
    "deliver_single",
    "schedule_cleanup",
    "schedule_group_delete",
    "send_file",
]
