"""Access gates: verification and force subscribe."""

from __future__ import annotations

import logging

from pyrogram import Client
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from services import verify
from services.settings import get_settings
from ui import keyboards as kb
from ui import texts

log = logging.getLogger(__name__)

Gate = tuple[str, InlineKeyboardMarkup]


async def verification_gate(user_id: int, resume: str) -> Gate | None:
    """Return a message to send when the user still has to verify."""
    if not await verify.needs_verification(user_id):
        return None
    _, url = await verify.begin(user_id, resume)
    return texts.VERIFY_REQUIRED, kb.verify_keyboard(url)


def _join_button(chat) -> InlineKeyboardButton | None:
    url = getattr(chat, "invite_link", None)
    if not url and getattr(chat, "username", None):
        url = f"https://t.me/{chat.username}"
    if not url:
        return None
    return InlineKeyboardButton(f"Join {chat.title}", url=url)


async def fsub_gate(client: Client, chat_id: int, user_id: int, resume: str = "") -> Gate | None:
    """Return a message when the user has not joined all fsub channels."""
    chat_settings = await get_settings(chat_id)
    channels = chat_settings.get("fsub") or []
    if not channels:
        return None

    buttons: list[InlineKeyboardButton] = []
    for channel_id in channels:
        try:
            member = await client.get_chat_member(int(channel_id), user_id)
            if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
                raise UserNotParticipant
        except UserNotParticipant:
            try:
                chat = await client.get_chat(int(channel_id))
            except Exception as error:  # noqa: BLE001 - bot may have been kicked
                log.warning("fsub channel %s unavailable: %s", channel_id, error)
                continue
            button = _join_button(chat)
            if button:
                buttons.append(button)
        except Exception as error:  # noqa: BLE001 - never block on API hiccups
            log.warning("fsub check failed for %s: %s", channel_id, error)

    if not buttons:
        return None
    return texts.FSUB_REQUIRED, kb.fsub_keyboard(buttons, resume)


async def check(client: Client, *, user_id: int, chat_id: int, resume: str) -> Gate | None:
    """Verification first, then force subscribe."""
    gate = await verification_gate(user_id, resume)
    if gate:
        return gate
    return await fsub_gate(client, chat_id, user_id, resume)


__all__ = ["Gate", "check", "fsub_gate", "verification_gate"]
