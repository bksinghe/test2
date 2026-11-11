"""Search inside the bot's private chat."""

from __future__ import annotations

import html
import logging

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup

from config import settings
from db import meta
from filters.guards import not_banned, not_command
from services import search as search_service
from services.registry import ensure_user
from services.search_flow import run_search
from ui import keyboards as kb
from ui import texts

log = logging.getLogger(__name__)

SEARCH_GROUP = 10


@Client.on_message(
    filters.private & filters.text & not_command & not_banned & filters.incoming,
    group=SEARCH_GROUP,
)
async def pm_search(client: Client, message):
    await ensure_user(client, message.from_user)

    if not await meta.pm_search_enabled(settings.pm_search):
        total = await search_service.count(message.text)
        body = (
            f"<b><i>🤗 ᴛᴏᴛᴀʟ <code>{total}</code> ʀᴇꜱᴜʟᴛꜱ ꜰᴏᴜɴᴅ 👇</i></b>"
            if total
            else "<b><i>📢 ꜱᴇɴᴅ ᴀ ᴍᴏᴠɪᴇ ᴏʀ ꜱᴇʀɪᴇꜱ ʀᴇǫᴜᴇꜱᴛ ʜᴇʀᴇ 👇</i></b>"
        )
        await message.reply_text(
            body,
            reply_markup=InlineKeyboardMarkup([[kb.button("🗂 ᴄʟɪᴄᴋ ʜᴇʀᴇ 🗂", url=settings.films_link)]]),
        )
        return

    placeholder = await message.reply_text(
        texts.SEARCHING.format(query=html.escape(message.text[:64]))
    )
    await run_search(
        client,
        chat_id=message.chat.id,
        query=message.text,
        viewer=message.from_user,
        chat_title=message.chat.title or "Private chat",
        placeholder=placeholder,
        reply_to_id=message.id,
    )


__all__ = ["pm_search"]
