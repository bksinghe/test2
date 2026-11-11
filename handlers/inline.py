"""Inline search (``@bot query``)."""

from __future__ import annotations

import logging

from pyrogram import Client
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultCachedDocument,
)

from config import settings
from core import state
from core.fmt import human_size
from core.telegram import safe_inline_answer
from services import search
from ui import texts

log = logging.getLogger(__name__)


def _reply_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⚡️ Updates", url=settings.updates_link),
                InlineKeyboardButton("💡 Support", url=settings.support_link),
            ]
        ]
    )


def _caption(file) -> str:
    template = settings.file_caption
    size = human_size(file.file_size)
    try:
        return template.format(
            file_name=file.file_name,
            file_size=size,
            size=size,
            file_caption=file.caption,
            caption=file.caption,
        )
    except (KeyError, IndexError, ValueError):
        return f"<b>{file.file_name}</b>\n<b>{size}</b>"


@Client.on_inline_query()
async def inline_search(client: Client, query: InlineQuery):
    if query.from_user and query.from_user.id in state.banned_users:
        await safe_inline_answer(
            query,
            results=[],
            cache_time=0,
            switch_pm_text=texts.INLINE_BANNED,
            switch_pm_parameter="start",
        )
        return

    text = (query.query or "").strip()
    offset = int(query.offset or 0)
    if not text:
        await safe_inline_answer(
            query,
            results=[],
            cache_time=0,
            switch_pm_text="Type a movie or series name",
            switch_pm_parameter="start",
        )
        return

    result = await search.search(text, offset=offset)
    results = [
        InlineQueryResultCachedDocument(
            title=file.file_name,
            document_file_id=file.file_id,
            caption=_caption(file),
            description=f"Size: {human_size(file.file_size)}",
            reply_markup=_reply_markup(),
        )
        for file in result.files
    ]

    if results:
        label = f"{texts.INLINE_RESULTS} - {result.total} for {text}"
        await safe_inline_answer(
            query,
            results=results,
            is_personal=True,
            cache_time=settings.cache_time,
            switch_pm_text=label,
            switch_pm_parameter="start",
            next_offset=str(result.next_offset),
        )
    else:
        await safe_inline_answer(
            query,
            results=[],
            is_personal=True,
            cache_time=settings.cache_time,
            switch_pm_text=f"{texts.INLINE_NO_RESULTS} for {text}",
            switch_pm_parameter="start",
        )


__all__ = ["inline_search"]
