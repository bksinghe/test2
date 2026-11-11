"""User/group registration with log channel notifications."""

from __future__ import annotations

import logging

from pyrogram import Client

from config import settings
from db import chats, users
from ui import texts

log = logging.getLogger(__name__)


async def _notify(client: Client, text: str) -> None:
    if not settings.log_channel:
        return
    try:
        await client.send_message(settings.log_channel, text)
    except Exception as error:  # noqa: BLE001 - logging must never break a flow
        log.warning("could not notify the log channel: %s", error)


async def ensure_user(client: Client, user) -> bool:
    """Register a user. Returns ``True`` when they are new."""
    if user is None:
        return False
    is_new = await users.add(user.id, user.first_name or str(user.id))
    if is_new:
        await _notify(client, texts.NEW_USER.format(mention=user.mention, user_id=user.id))
    return is_new


async def ensure_chat(client: Client, chat, members: int | None = None) -> bool:
    """Register a group. Returns ``True`` when it is new."""
    if chat is None:
        return False
    is_new = await chats.add(chat.id, chat.title or str(chat.id))
    if is_new:
        if members is None:
            try:
                members = await client.get_chat_members_count(chat.id)
            except Exception:  # noqa: BLE001
                members = 0
        username = f"@{chat.username}" if chat.username else "private"
        await _notify(
            client,
            texts.NEW_GROUP.format(
                title=chat.title, chat_id=chat.id, username=username, members=members or 0
            ),
        )
    return is_new


__all__ = ["ensure_chat", "ensure_user"]
