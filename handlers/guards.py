"""Banned user / disabled chat guards.

Registered in group ``-10`` (first) and they raise ``StopPropagation`` so no
other handler reacts to the same update. This replaces the old ``banned.py``
filters, which raised ``AttributeError`` for channel posts and were evaluated
in an unpredictable order.
"""

from __future__ import annotations

import logging

from pyrogram import Client, StopPropagation, filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup

from config import settings
from db import chats, users
from filters.guards import banned_user, disabled_chat
from ui import keyboards as kb
from ui import texts

log = logging.getLogger(__name__)

GUARD_GROUP = -10


@Client.on_message(filters.private & banned_user, group=GUARD_GROUP)
async def banned_guard(client: Client, message):
    status = await users.ban_status(message.from_user.id)
    await message.reply(
        texts.BANNED_NOTICE.format(
            mention=message.from_user.mention, reason=status.get("reason") or "-"
        ),
        reply_markup=InlineKeyboardMarkup([[kb.button("Support group", url=settings.support_link)]]),
        parse_mode=ParseMode.HTML,
    )
    raise StopPropagation


@Client.on_message(filters.group & disabled_chat, group=GUARD_GROUP)
async def disabled_chat_guard(client: Client, message):
    status = await chats.status(message.chat.id)
    notice = await message.reply(
        texts.CHAT_DISABLED_NOTICE.format(reason=status.get("reason") or "-"),
        reply_markup=InlineKeyboardMarkup([[kb.button("Support group", url=settings.support_link)]]),
        parse_mode=ParseMode.HTML,
    )
    try:
        await notice.pin()
    except Exception:  # noqa: BLE001 - pinning is optional
        pass
    try:
        await client.leave_chat(message.chat.id)
    except Exception as error:  # noqa: BLE001
        log.debug("could not leave %s: %s", message.chat.id, error)
    raise StopPropagation


__all__ = ["GUARD_GROUP", "banned_guard", "disabled_chat_guard"]
