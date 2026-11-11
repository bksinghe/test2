"""The single place that renders a result page.

The old code had six copy/pasted versions of this logic (main page, language
page, language next page, quality page, quality next page, first page). They
drifted apart and shared ~370 duplicated lines. One builder now serves every
path: first page, pagination and filtered pages.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

from pyrogram.types import InlineKeyboardMarkup

from config import settings
from core import state
from core.fmt import human_size, readable_time
from db.media import MediaFile
from services import premium, shortlink
from services import search as search_service
from services.settings import get_settings
from ui import keyboards as kb
from ui import texts

# how many buttons can live in one message before Telegram complains
MAX_ROWS = 100


@dataclass(slots=True)
class Page:
    text: str
    keyboard: InlineKeyboardMarkup
    files: list[MediaFile]
    total: int
    offset: int
    page: int
    pages: int
    next_offset: int | str


def file_link(chat_id: int, file: MediaFile) -> str:
    return f"https://t.me/{state.username or 'bot'}?start=file_{chat_id}_{file.file_id}"


def _links_block(chat_id: int, files: list[MediaFile]) -> str:
    return "".join(
        f"\n\n📁 <a href={file_link(chat_id, file)}>[{human_size(file.file_size)}] "
        f"{html.escape(file.file_name)}</a>"
        for file in files
    )


def _file_rows(files: list[MediaFile]) -> list[list]:
    return [
        [kb.button(f"📂 {human_size(file.file_size)} {file.file_name}", f"file#{file.file_id}")]
        for file in files[:MAX_ROWS]
    ]


async def render_page(
    session: state.SearchSession,
    *,
    viewer_id: int,
    offset: int = 0,
    lang: str = "",
    quality: str = "",
) -> Page:
    """Search and build the page for ``session.query``."""
    chat_settings = await get_settings(session.chat_id)
    result = await search_service.search(
        session.query, offset=offset, lang=lang, quality=quality
    )
    is_premium = await premium.has_premium(viewer_id)

    rows: list[list] = []
    if chat_settings["links"]:
        links = _links_block(session.chat_id, result.files)
        file_rows: list[list] = []
    else:
        links = ""
        file_rows = _file_rows(result.files)

    send_all_row = [kb.button("📰 Languages", f"filtermenu#lang#{session.key}#{viewer_id}#{offset}")]
    if chat_settings["shortlink"] and not is_premium:
        wrapped = await shortlink.shorten(
            chat_settings["url"],
            chat_settings["api"],
            f"https://t.me/{state.username or 'bot'}?start=all_{session.chat_id}_{session.key}",
        )
        if wrapped:
            send_all_row.append(kb.button("♻️ Send all", url=wrapped))
        else:
            send_all_row.append(kb.button("♻️ Send all", f"sendall#{session.key}#{viewer_id}"))
    else:
        send_all_row.append(
            kb.button("♻️ Send all", f"sendall#{session.key}#{viewer_id}")
        )
    send_all_row.append(
        kb.button("⚙️ Quality", f"filtermenu#qual#{session.key}#{viewer_id}#{offset}")
    )
    rows.append(send_all_row)

    if chat_settings["shortlink"] and not is_premium:
        rows.append([kb.button("💰 Buy premium", "menu#plans")])

    rows.extend(file_rows)
    rows.append(
        kb.pagination_row(
            session.key,
            viewer_id,
            offset,
            result.next_offset,
            result.page,
            result.pages,
            filter_type="lang" if lang else ("qual" if quality else ""),
            filter_value=lang or quality,
        )
    )
    if lang or quality:
        rows.append([kb.button("🏄 Back to all results", f"nav#{session.key}#{viewer_id}#0")])

    notice = ""
    if chat_settings["auto_delete"]:
        notice = texts.AUTO_DELETE_NOTICE.format(delay=readable_time(settings.delete_time))

    text = f"{session.caption}{links}{notice}"[:4096]
    return Page(
        text=text,
        keyboard=InlineKeyboardMarkup(rows),
        files=result.files,
        total=result.total,
        offset=result.offset,
        page=result.page,
        pages=result.pages,
        next_offset=result.next_offset,
    )


__all__ = ["MAX_ROWS", "Page", "file_link", "render_page"]
