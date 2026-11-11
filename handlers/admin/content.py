"""Index maintenance: delete by query and delete everything."""

from __future__ import annotations

import logging
import secrets

from pyrogram import Client, filters
from pyrogram.enums import ParseMode

from core import state
from core.telegram import safe_answer, safe_edit
from db import media
from handlers.common import react
from services import search
from services.rights import is_bot_admin
from ui import keyboards as kb
from ui import texts

log = logging.getLogger(__name__)

ADMIN_GROUP = 0


def _is_admin(query_or_message) -> bool:
    user = getattr(query_or_message, "from_user", None)
    return is_bot_admin(user.id if user else None)


@Client.on_message(filters.command("delete"), group=ADMIN_GROUP)
async def delete_cmd(client: Client, message):
    await react(message)
    if not _is_admin(message):
        await message.reply_text(texts.NOT_ADMIN)
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.reply_text(texts.COMMAND_INCOMPLETE.format(usage="/delete &lt;query&gt;"))
        return

    query = parts[1].strip()
    total, filt = await search.delete_matching(query)
    if total == 0:
        await message.reply_text(texts.DELETE_NONE)
        return

    token = secrets.token_urlsafe(6)
    state.delete_cache.set(token, (query, filt))
    await message.reply_text(
        texts.DELETE_PREVIEW.format(total=total, query=query),
        reply_markup=kb.confirm_keyboard(f"delconfirm#{token}"),
        parse_mode=ParseMode.HTML,
    )


@Client.on_callback_query(filters.regex(r"^delconfirm#"), group=ADMIN_GROUP)
async def delete_confirm(client: Client, query):
    if not _is_admin(query):
        await safe_answer(query, texts.ADMIN_ONLY_BUTTON, show_alert=True)
        return
    token = query.data.split("#", 1)[1]
    pending = state.delete_cache.pop(token)
    if pending is None:
        await safe_answer(query, texts.DELETE_CONFIRM_EXPIRED, show_alert=True)
        return
    query_text, filt = pending
    count = await media.delete(filt)
    await safe_edit(query.message, texts.DELETE_DONE.format(count=count, query=query_text))


@Client.on_message(filters.command("delete_all"), group=ADMIN_GROUP)
async def delete_all_cmd(client: Client, message):
    await react(message)
    if not _is_admin(message):
        await message.reply_text(texts.NOT_ADMIN)
        return
    total = await media.count()
    if total == 0:
        await message.reply_text(texts.DELETE_ALL_EMPTY)
        return
    await message.reply_text(
        texts.DELETE_ALL_PREVIEW.format(total=total),
        reply_markup=kb.confirm_keyboard("deleteall"),
        parse_mode=ParseMode.HTML,
    )


@Client.on_callback_query(filters.regex(r"^deleteall$"), group=ADMIN_GROUP)
async def delete_all_confirm(client: Client, query):
    if not _is_admin(query):
        await safe_answer(query, texts.ADMIN_ONLY_BUTTON, show_alert=True)
        return
    await safe_answer(query)
    removed = await media.drop()
    await safe_edit(query.message, texts.DELETE_ALL_DONE.format(count=removed))


__all__ = ["delete_all_cmd", "delete_all_confirm", "delete_cmd", "delete_confirm"]
