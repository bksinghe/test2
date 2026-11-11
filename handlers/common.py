"""Small helpers shared by handlers (not a plugin: registers no handlers)."""

from __future__ import annotations

import logging
import random

from pyrogram import Client
from pyrogram.enums import ChatType, ParseMode
from pyrogram.types import Message

from config import settings
from core import state
from core.telegram import SEND_IMPOSSIBLE, safe_react, safe_send
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
    """Celebrate a command; never let a failed reaction break the handler."""
    reactions = settings.reactions or ("🔥",)
    picks = [random.choice(reactions)]
    if "⚡️" not in picks:
        picks.append("⚡️")
    await safe_react(message, picks)


async def group_admin_guard(client: Client, message: Message) -> bool:
    """Validate that the sender may configure the current group."""
    if message.from_user is None:
        await safe_send(message.chat.id, texts.ANONYMOUS_ADMIN, client=client)
        return False
    if message.chat.type not in GROUP_TYPES:
        await safe_send(message.chat.id, texts.GROUP_ONLY, client=client)
        return False
    if not await is_chat_admin(client, message.chat.id, message.from_user.id):
        await safe_send(message.chat.id, texts.NOT_GROUP_ADMIN, client=client)
        return False
    return True


async def send_plans(
    client: Client, chat_id: int, reply_to_id: int | None = None
) -> Message | None:
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
        except SEND_IMPOSSIBLE as error:
            log.debug("plans not delivered to %s: %s", chat_id, error)
            return None
        except Exception as error:  # noqa: BLE001 - fall back to text
            log.debug("payment qr could not be sent (%s), using text", error)
    return await safe_send(chat_id, text, markup, client=client, reply_to=reply_to_id)


async def send_start(client: Client, message: Message) -> Message | None:
    text = texts.START_TEXT.format(mention=message.from_user.mention, wish=texts.greeting())
    markup = kb.start_keyboard()
    if settings.pics:
        try:
            return await client.send_photo(
                chat_id=message.chat.id,
                photo=random.choice(settings.pics),
                caption=text,
                reply_markup=markup,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=message.id,
            )
        except SEND_IMPOSSIBLE as error:
            # blocked bots / kicked chats: nothing to do, and no traceback
            log.debug("start photo not delivered: %s", error)
            return None
        except Exception as error:  # noqa: BLE001 - fall back to plain text
            log.debug("start photo failed (%s), sending text", error)
    return await safe_send(
        message.chat.id, text, markup, client=client, reply_to=message.id
    )


async def premium_line(user_id: int) -> str:
    if await premium.has_premium(user_id):
        return "premium"
    return "free"


__all__ = [
    "GROUP_TYPES",
    "group_admin_guard",
    "premium_line",
    "react",
    "send_plans",
    "send_start",
]
