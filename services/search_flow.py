"""The shared search pipeline used by PM search, group search and spell check.

Keeping this in one place is what removes the biggest chunk of duplicated code
from the old ``pm_filter.py``.
"""

from __future__ import annotations

import html
import logging
import secrets
from typing import Any

from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.errors import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from pyrogram.types import InlineKeyboardMarkup, Message

from config import settings
from core import state
from services import delivery, imdb, render
from services import search as search_service
from services.settings import get_settings
from ui import keyboards as kb
from ui import texts

log = logging.getLogger(__name__)


def new_key() -> str:
    return secrets.token_urlsafe(8)


def build_caption(
    *,
    query: str,
    total: int,
    chat_settings: dict[str, Any],
    viewer,
    chat_title: str,
    imdb_data: dict[str, Any] | None,
) -> str:
    mention = getattr(viewer, "mention", None) or "friend"
    if not imdb_data:
        return texts.RESULT_FOOTER.format(query=query, total=total, mention=mention)

    template = chat_settings.get("template") or settings.imdb_template
    context: dict[str, Any] = {
        **imdb_data,
        "query": query,
        "total": total,
        "total_results": total,
        "mention": mention,
        "chat_title": chat_title,
        "message": _MessageProxy(mention=mention, chat_title=chat_title),
    }
    try:
        return template.format(**context)
    except (KeyError, IndexError, ValueError):
        log.warning("invalid IMDb template, falling back to the default")
        return texts.RESULT_FOOTER.format(query=query, total=total, mention=mention)


class _UserProxy:
    __slots__ = ("mention",)

    def __init__(self, mention: str) -> None:
        self.mention = mention


class _ChatProxy:
    __slots__ = ("title",)

    def __init__(self, title: str) -> None:
        self.title = title


class _MessageProxy:
    """Lets legacy templates keep using ``{message.from_user.mention}`` etc."""

    __slots__ = ("from_user", "chat")

    def __init__(self, mention: str, chat_title: str) -> None:
        self.from_user = _UserProxy(mention)
        self.chat = _ChatProxy(chat_title)


async def run_search(
    client: Client,
    *,
    chat_id: int,
    query: str,
    viewer,
    chat_title: str = "",
    placeholder: Message | None = None,
    reply_to_id: int | None = None,
    chat_settings: dict[str, Any] | None = None,
) -> Message | None:
    """Search ``query`` and render the first page (or a suggestion list)."""
    chat_settings = chat_settings or await get_settings(chat_id)
    result = await search_service.search(query)

    if not result.files:
        await _nothing_found(
            client,
            chat_id=chat_id,
            query=query,
            viewer=viewer,
            chat_title=chat_title,
            placeholder=placeholder,
            chat_settings=chat_settings,
            reply_to_id=reply_to_id,
        )
        return None

    imdb_data = None
    if chat_settings["imdb"]:
        imdb_data = await imdb.details(query, file_name=result.files[0].file_name)

    session = state.SearchSession(
        key=new_key(),
        query=query,
        chat_id=chat_id,
        caption=build_caption(
            query=query,
            total=result.total,
            chat_settings=chat_settings,
            viewer=viewer,
            chat_title=chat_title,
            imdb_data=imdb_data,
        ),
        total=result.total,
    )
    state.search_cache.set(session.key, session)
    page = await render.render_page(session, viewer_id=getattr(viewer, "id", 0))
    return await send_page(
        client,
        chat_id=chat_id,
        page=page,
        session=session,
        imdb_data=imdb_data,
        placeholder=placeholder,
        reply_to_id=reply_to_id,
        chat_settings=chat_settings,
    )


async def send_page(
    client: Client,
    *,
    chat_id: int,
    page: render.Page,
    session: state.SearchSession,
    imdb_data: dict[str, Any] | None = None,
    placeholder: Message | None = None,
    reply_to_id: int | None = None,
    chat_settings: dict[str, Any] | None = None,
    edit: bool = False,
) -> Message | None:
    """Send the page as a photo (IMDb poster) or as text, editing in place."""
    if edit and placeholder is not None:
        return await placeholder.edit_text(
            page.text,
            reply_markup=page.keyboard,
            disable_web_page_preview=True,
            parse_mode=ParseMode.HTML,
        )

    if imdb_data and imdb_data.get("poster"):
        photo_message = await _send_photo(
            client,
            chat_id=chat_id,
            page=page,
            poster=imdb_data["poster"],
            reply_to_id=reply_to_id,
        )
        if photo_message is not None:
            if placeholder is not None:
                await _safe_delete(client, chat_id, placeholder.id)
            return photo_message

    if placeholder is not None:
        return await placeholder.edit_text(
            page.text,
            reply_markup=page.keyboard,
            disable_web_page_preview=True,
            parse_mode=ParseMode.HTML,
        )
    return await client.send_message(
        chat_id=chat_id,
        text=page.text,
        reply_markup=page.keyboard,
        disable_web_page_preview=True,
        parse_mode=ParseMode.HTML,
        reply_to_message_id=reply_to_id,
    )


async def _send_photo(
    client: Client,
    *,
    chat_id: int,
    page: render.Page,
    poster: str,
    reply_to_id: int | None,
) -> Message | None:
    caption = page.text[:1024]
    candidates = (poster, poster.replace(".jpg", "._V1_UX360.jpg"))
    for url in candidates:
        try:
            return await client.send_photo(
                chat_id=chat_id,
                photo=url,
                caption=caption,
                reply_markup=page.keyboard,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=reply_to_id,
            )
        except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
            continue
        except Exception as error:  # noqa: BLE001 - fall back to a text result
            log.warning("poster send failed: %s", error)
            break
    return None


async def _safe_delete(client: Client, chat_id: int, message_id: int) -> None:
    try:
        await client.delete_messages(chat_id=chat_id, message_ids=message_id)
    except Exception:  # noqa: BLE001
        pass


async def _nothing_found(
    client: Client,
    *,
    chat_id: int,
    query: str,
    viewer,
    chat_title: str,
    placeholder: Message | None,
    chat_settings: dict[str, Any],
    reply_to_id: int | None,
) -> None:
    mention = getattr(viewer, "mention", None) or "friend"
    if chat_settings["spell_check"]:
        movies = await imdb.suggestions(query)
        if movies:
            buttons = [
                [kb.button(movie["title"] + (f" ({movie['year']})" if movie.get("year") else ""),
                           f"suggest#{movie['id']}#{getattr(viewer, 'id', 0)}")]
                for movie in movies[:8]
            ]
            buttons.append(kb.close_row())
            text = texts.SUGGESTIONS.format(mention=mention, query=html.escape(query))
            if placeholder is not None:
                sent = await placeholder.edit_text(
                    text, reply_markup=InlineKeyboardMarkup(buttons)
                )
            else:
                sent = await client.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    reply_to_message_id=reply_to_id,
                )
            delivery.schedule_cleanup(client, chat_id=chat_id, message_ids=[sent.id], delay=300)
            return

    google = query.replace(" ", "+")
    buttons = InlineKeyboardMarkup(
        [
            [
                kb.button("⚠️ Instructions ⚠️", "instructions"),
                kb.button("🔎 Search on Google", url=f"https://www.google.com/search?q={google}"),
            ],
            kb.close_row(),
        ]
    )
    text = texts.NOT_FOUND.format(mention=mention, query=html.escape(query))
    if placeholder is not None:
        sent = await placeholder.edit_text(text, reply_markup=buttons)
    else:
        sent = await client.send_message(
            chat_id=chat_id, text=text, reply_markup=buttons, reply_to_message_id=reply_to_id
        )
    delivery.schedule_cleanup(client, chat_id=chat_id, message_ids=[sent.id], delay=60)


__all__ = ["build_caption", "new_key", "run_search", "send_page"]
