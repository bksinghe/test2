"""Small helpers shared by handlers (not a plugin: registers no handlers)."""

from __future__ import annotations

import logging
import random

from pyrogram import Client
from pyrogram.enums import ChatType, ParseMode
from pyrogram.errors import MessageNotModified
from pyrogram.types import Message

from config import settings
from core import state
from services import premium
from services.rights import is_chat_admin
from ui import keyboards as kb
from ui import texts

log = logging.getLogger(__name__)

GROUP_TYPES = (ChatType.GROUP, ChatType.SUPERGROUP)


def bot_link(payload: str = "") -> str | None:
    """``https://t.me/<bot>?start=<payload>`` or ``None`` while the username is unknown."""
    if not state.username:
        return None
    return f"https://t.me/{state.username}" + (f"?start={payload}" if payload else "")


async def react(message: Message) -> None:
    reactions = settings.reactions or ("🔥",)
    try:
        await message.react(emoji=random.choice(reactions), big=True)
    except Exception:  # noqa: BLE001 - reactions are cosmetic
        pass


async def group_admin_guard(client: Client, message: Message) -> bool:
    """Validate that the sender may configure the current group."""
    if message.from_user is None:
        await message.reply(texts.ANONYMOUS_ADMIN)
        return False
    if message.chat.type not in GROUP_TYPES:
        await message.reply(texts.GROUP_ONLY)
        return False
    if not await is_chat_admin(client, message.chat.id, message.from_user.id):
        await message.reply(texts.NOT_GROUP_ADMIN)
        return False
    return True


async def send_plans(client: Client, chat_id: int, reply_to_id: int | None = None) -> Message:
    text = texts.PLANS.format(upi=settings.owner_upi)
    markup = kb.plans_keyboard()
    if settings.payment_qr:
        try:
            return await client.send_photo(
                chat_id=chat_id,
                photo=settings.payment_qr,
                caption=text,
                reply_markup=markup,
                parse_mode=ParseMode.HTML,
            )
        except Exception as error:  # noqa: BLE001 - fall back to text
            log.warning("payment qr could not be sent: %s", error)
    return await client.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=markup,
        parse_mode=ParseMode.HTML,
        reply_to_message_id=reply_to_id,
    )


async def send_start(client: Client, message: Message) -> Message:
    text = texts.START_TEXT.format(mention=message.from_user.mention, wish=texts.greeting())
    if settings.pics:
        return await message.reply_photo(
            photo=random.choice(settings.pics),
            caption=text,
            reply_markup=kb.start_keyboard(),
            parse_mode=ParseMode.HTML,
        )
    return await message.reply_text(
        text, reply_markup=kb.start_keyboard(), parse_mode=ParseMode.HTML
    )


async def safe_edit(message: Message, text: str, markup=None) -> None:
    try:
        await message.edit_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    except MessageNotModified:
        pass


async def premium_line(user_id: int) -> str:
    if await premium.has_premium(user_id):
        return "premium"
    return "free"


__all__ = [
    "GROUP_TYPES",
    "group_admin_guard",
    "premium_line",
    "react",
    "safe_edit",
    "send_plans",
    "send_start",
]
