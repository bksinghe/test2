"""Manual channel indexing (forward a post or send a t.me link)."""

from __future__ import annotations

import logging
import time

from pyrogram import Client, StopPropagation, filters
from pyrogram.enums import ChatType, ParseMode
from pyrogram.types import InlineKeyboardMarkup, Message

from core import state
from core.fmt import readable_time
from services import deeplink, indexer
from services.rights import is_bot_admin
from ui import keyboards as kb
from ui import texts

log = logging.getLogger(__name__)

ADMIN_GROUP = 0
LISTEN_TIMEOUT = 180

def is_bot_admin_message(message: Message) -> bool:
    return is_bot_admin(message.from_user.id if message.from_user else None)


def _cancel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[kb.button("CANCEL", "index#cancel")]])


@Client.on_message(
    filters.private
    & filters.incoming
    & (filters.forwarded | filters.regex(r"^https?://t\.me/"))
    & filters.create(lambda _, __, m: is_bot_admin_message(m), "BotAdmin"),
    group=ADMIN_GROUP,
)
async def index_request(client: Client, message: Message):
    # stop propagation so the generic PM search handler does not also answer
    try:
        await _handle_request(client, message)
    except StopPropagation:
        raise
    except Exception:  # noqa: BLE001
        log.exception("index request failed")
    raise StopPropagation


async def _handle_request(client: Client, message: Message) -> None:
    if state.index_lock.locked():
        await message.reply_text(texts.INDEX_BUSY)
        return

    link = deeplink.parse_channel_link(message.text or "")
    if link:
        chat_ref, last_id = link
    elif message.forward_from_chat is not None:
        chat_ref = message.forward_from_chat.username or message.forward_from_chat.id
        last_id = message.forward_from_message_id
    else:
        await message.reply_text(texts.INDEX_USAGE)
        return

    try:
        chat = await client.get_chat(chat_ref)
    except Exception as error:  # noqa: BLE001
        await message.reply_text(f"Cannot access that chat: {error}")
        return
    if chat.type != ChatType.CHANNEL:
        await message.reply_text(texts.INDEX_ONLY_CHANNELS)
        return

    prompt = await message.reply_text(texts.INDEX_SKIP_PROMPT)
    try:
        answer = await client.listen(
            chat_id=message.chat.id, user_id=message.from_user.id, timeout=LISTEN_TIMEOUT
        )
    except TimeoutError:
        answer = None
    await prompt.delete()
    if answer is None or not answer.text:
        await message.reply_text("Timed out waiting for the skip number.")
        return
    try:
        skip = int(answer.text.strip())
    except ValueError:
        await message.reply_text(texts.INDEX_SKIP_INVALID)
        return

    await message.reply_text(
        texts.INDEX_CONFIRM.format(title=chat.title, last_id=last_id),
        reply_markup=kb.index_confirm_keyboard(chat_ref, last_id, skip),
        parse_mode=ParseMode.HTML,
    )


@Client.on_callback_query(filters.regex(r"^index#"), group=ADMIN_GROUP)
async def index_callback(client: Client, query):
    if not is_bot_admin(query.from_user.id):
        await query.answer(texts.ADMIN_ONLY_BUTTON, show_alert=True)
        return

    parts = query.data.split("#")
    action = parts[1] if len(parts) > 1 else ""

    if action == "cancel":
        state.index_cancel = True
        await query.answer("Cancelling…")
        return
    if action != "yes" or len(parts) != 5:
        await query.answer(texts.SOMETHING_WRONG, show_alert=True)
        return

    chat_ref = parts[2]
    chat_id: int | str = int(chat_ref) if chat_ref.lstrip("-").isdigit() else chat_ref
    last_id, skip = int(parts[3]), int(parts[4])

    if state.index_lock.locked():
        await query.answer(texts.INDEX_BUSY, show_alert=True)
        return

    await query.answer()
    status = query.message
    await status.edit_text(texts.INDEX_STARTED)
    started = time.time()

    async def progress(stats: indexer.IndexStats) -> None:
        await status.edit_text(
            texts.INDEX_PROGRESS.format(
                title=chat_ref, current=stats.current, saved=stats.saved,
                duplicates=stats.duplicates, deleted=stats.deleted,
                skipped=stats.skipped, errors=stats.errors,
            ),
            reply_markup=_cancel_markup(),
            parse_mode=ParseMode.HTML,
        )

    async with state.index_lock:
        stats = await indexer.index_range(
            client, chat_id=chat_id, last_message_id=last_id, skip=skip, progress=progress
        )

    duration = readable_time(time.time() - started)
    template = texts.INDEX_CANCELLED if state.index_cancel else texts.INDEX_DONE
    if template is texts.INDEX_CANCELLED:
        body = template.format(saved=stats.saved)
    else:
        body = template.format(
            duration=duration, saved=stats.saved, duplicates=stats.duplicates,
            deleted=stats.deleted, skipped=stats.skipped, errors=stats.errors,
        )
    await status.edit_text(body, parse_mode=ParseMode.HTML)


__all__ = ["index_callback", "index_request"]
