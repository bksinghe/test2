"""Admin checks."""

from __future__ import annotations

import logging

from pyrogram import Client
from pyrogram.enums import ChatMemberStatus, ChatType

from config import settings

log = logging.getLogger(__name__)

ADMIN_STATUSES = (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)


def is_bot_admin(user_id: int | None) -> bool:
    return settings.is_admin(user_id)


async def is_chat_admin(client: Client, chat_id: int, user_id: int | None) -> bool:
    if not user_id:
        return False
    try:
        member = await client.get_chat_member(chat_id, user_id)
    except Exception as error:  # noqa: BLE001 - private chat / not a member
        log.debug("admin check failed in %s: %s", chat_id, error)
        return False
    return member.status in ADMIN_STATUSES


async def is_chat_admin_in(client: Client, chat, user_id: int | None) -> bool:
    if getattr(chat, "type", None) not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return False
    return await is_chat_admin(client, chat.id, user_id)


__all__ = ["ADMIN_STATUSES", "is_bot_admin", "is_chat_admin", "is_chat_admin_in"]
