"""Greeting when the bot is added and welcome messages for new members.

The join detection is fixed: the old code required ``old_chat_member`` to be
falsy, but Telegram always sends the previous state (``LEFT``/``BANNED``), so
welcome messages never went out.
"""

from __future__ import annotations

import logging
import random

from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus, ParseMode

from config import settings
from core import state
from services.registry import ensure_chat
from services.settings import get_settings
from ui import keyboards as kb
from ui import texts

log = logging.getLogger(__name__)

PRESENT = (
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.OWNER,
)


@Client.on_chat_member_updated(filters.group, group=0)
async def member_updated(client: Client, update):
    new = update.new_chat_member
    if new is None or new.status not in PRESENT:
        return

    old_status = update.old_chat_member.status if update.old_chat_member else None
    if old_status in PRESENT:
        return  # a promotion/rank change, not a join

    user = new.user
    if user is None:
        return

    if user.id == state.me:
        await _bot_added(client, update)
        return

    chat_settings = await get_settings(update.chat.id)
    if not chat_settings["welcome"] or not chat_settings["welcome_text"]:
        return

    try:
        text = chat_settings["welcome_text"].format(
            mention=user.mention, title=update.chat.title, first_name=user.first_name
        )
    except (KeyError, IndexError, ValueError):
        log.warning("invalid welcome text in %s", update.chat.id)
        return

    try:
        await client.send_message(update.chat.id, text, parse_mode=ParseMode.HTML)
    except Exception as error:  # noqa: BLE001
        log.debug("welcome message failed in %s: %s", update.chat.id, error)


async def _bot_added(client: Client, update) -> None:
    await ensure_chat(client, update.chat)
    mention = update.from_user.mention if update.from_user else "friend"
    text = texts.WELCOME_BOT_ADDED.format(mention=mention, title=update.chat.title)
    markup = kb.group_start_keyboard()
    try:
        if settings.pics:
            await client.send_photo(
                update.chat.id,
                photo=random.choice(settings.pics),
                caption=text,
                reply_markup=markup,
                parse_mode=ParseMode.HTML,
            )
        else:
            await client.send_message(
                update.chat.id, text, reply_markup=markup, parse_mode=ParseMode.HTML
            )
    except Exception as error:  # noqa: BLE001
        log.debug("could not greet in %s: %s", update.chat.id, error)


__all__ = ["member_updated"]
