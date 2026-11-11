"""``/start``: welcome screen and every deep link entry point."""

from __future__ import annotations

import logging

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup

from config import settings
from core import state
from core.fmt import readable_time
from core.telegram import SEND_IMPOSSIBLE
from db import media
from handlers.common import GROUP_TYPES, react, send_plans, send_start
from services import deeplink, delivery, gates, premium, search, verify
from services import shortlink as shortlink_service
from services.registry import ensure_chat, ensure_user
from services.settings import get_settings
from ui import keyboards as kb
from ui import texts

log = logging.getLogger(__name__)


@Client.on_message(filters.command("start") & filters.incoming, group=0)
async def start_handler(client: Client, message):
    await react(message)
    if message.chat.type in GROUP_TYPES:
        await _group_start(client, message)
        return
    await _private_start(client, message)


async def _group_start(client: Client, message) -> None:
    await ensure_chat(client, message.chat, members=None)
    await message.reply_text(
        texts.GROUP_START_TEXT.format(
            mention=message.from_user.mention if message.from_user else "friend",
            wish=texts.greeting(),
        ),
        reply_markup=kb.group_start_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def _private_start(client: Client, message) -> None:
    user = message.from_user
    await ensure_user(client, user)

    raw = message.command[1] if len(message.command) > 1 else ""
    payload = deeplink.parse(raw)

    if payload.kind in (deeplink.HOME, deeplink.UNKNOWN):
        await send_start(client, message)
    elif payload.kind == deeplink.PLANS:
        await send_plans(client, message.chat.id, message.id)
    elif payload.kind in (deeplink.VERIFY, deeplink.INLINE_VERIFY):
        await _confirm_verification(message, payload)
    elif payload.is_delivery:
        await _deliver(client, message, payload)


async def _confirm_verification(message, payload) -> None:
    resume = await verify.confirm(message.from_user.id, payload.token)
    if resume is None:
        await message.reply_text(texts.INVALID_TOKEN)
        return

    markup = None
    if payload.kind == deeplink.VERIFY and resume:
        markup = kb.post_verify_keyboard(resume)
    await message.reply_text(
        texts.VERIFIED.format(duration=readable_time(settings.verify_expire)),
        reply_markup=markup,
        protect_content=True,
    )


async def _deliver(client: Client, message, payload: deeplink.StartPayload) -> None:
    user_id = message.from_user.id
    group_id = payload.group_id or 0
    chat_settings = await get_settings(group_id)

    gate = await gates.check(
        client, user_id=user_id, chat_id=group_id, resume=payload.resume
    )
    if gate:
        text, markup = gate
        await message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        return

    if payload.kind == deeplink.ALL:
        await _deliver_all(client, message, payload, chat_settings)
        return

    file = await media.get(payload.file_id)
    if file is None:
        await message.reply_text(texts.INVALID_LINK)
        return

    if (  # noqa: SIM102 - guard and action are clearer apart
        payload.kind != deeplink.SHORTLINK
        and chat_settings["shortlink"]
        and not await premium.has_premium(user_id)
    ):
        if await _send_shortlink(message, payload, chat_settings, file):
            return

    try:
        await delivery.deliver_single(
            client,
            chat_id=message.chat.id,
            group_id=group_id,
            file=file,
            chat_settings=chat_settings,
        )
    except SEND_IMPOSSIBLE as error:
        # the user blocked the bot between the button press and the delivery
        log.debug("file %s not delivered: %s", file.file_id, error)
    except Exception as error:  # noqa: BLE001 - a stale file id must not crash
        log.warning("delivery of %s failed: %s", file.file_id, error)
        await message.reply_text(texts.SOMETHING_WRONG)


async def _send_shortlink(message, payload, chat_settings, file) -> bool:
    target = (
        f"https://t.me/{state.username or 'bot'}?start=shortlink_"
        f"{payload.group_id}_{file.file_id}"
    )
    url = await shortlink_service.shorten(chat_settings["url"], chat_settings["api"], target)
    if not url:
        return False
    markup = InlineKeyboardMarkup(
        [
            [kb.button("♻️ Get file ♻️", url=url)],
            [kb.button("📍 How to open the link 📍", url=chat_settings["tutorial"])],
        ]
    )
    await message.reply_text(
        f"[{file.file_name}]\n\nYour file is ready, use the button below. 👍",
        reply_markup=markup,
        protect_content=True,
        parse_mode=ParseMode.HTML,
    )
    return True


async def _deliver_all(client: Client, message, payload, chat_settings) -> None:
    session = state.search_cache.get(payload.key)
    if session is None:
        await message.reply_text(texts.INVALID_LINK)
        return
    files = await search.find_all(session.query)
    await delivery.deliver_all(
        client,
        chat_id=message.chat.id,
        group_id=payload.group_id or 0,
        files=files,
        chat_settings=chat_settings,
        token=payload.key,
    )


__all__ = ["start_handler"]
