"""Every callback owned by the search/menu UI.

The filter only matches this module's own prefixes, so the moderation,
broadcast and index modules can keep their own callback handlers without
depending on registration order.
"""

from __future__ import annotations

import html
import logging

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified

from config import settings
from core import state
from handlers.common import bot_link
from services import (
    deeplink,
    gates,
    imdb,
    premium,
    render,
    search_flow,
    streaming,
)
from services.rights import is_chat_admin
from services.settings import get_settings, update_setting
from ui import keyboards as kb
from ui import texts

log = logging.getLogger(__name__)

CALLBACK_RE = (
    r"^(close$|noop$|instructions$|trial$|menu#|settings#|nav#|navf#|"
    r"filtermenu#|filter#|sendall#|file#|regain#|stream#|checksub#|suggest#)"
)


def _viewer_ok(query, requested: str | int) -> bool:
    return int(requested) == 0 or query.from_user.id == int(requested)


async def _open_link(query, payload: str) -> bool:
    """Answer a callback by opening the bot with ``payload``; ``False`` if impossible."""
    url = bot_link(payload)
    if url is None:
        await query.answer(texts.SOMETHING_WRONG, show_alert=True)
        return False
    await query.answer(url=url)
    return True


def _int(value: str) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


async def _edit(query, text: str, markup=None) -> None:
    """Edit a text message or, when it is a photo, its caption."""
    try:
        if query.message.photo or query.message.video:
            await query.message.edit_caption(
                caption=text, reply_markup=markup, parse_mode=ParseMode.HTML
            )
        else:
            await query.message.edit_text(
                text,
                reply_markup=markup,
                disable_web_page_preview=True,
                parse_mode=ParseMode.HTML,
            )
    except MessageNotModified:
        pass


@Client.on_callback_query(filters.regex(CALLBACK_RE), group=0)
async def on_callback(client: Client, query):
    data = query.data

    if data == "close":
        await _close(query)
    elif data == "noop":
        await query.answer("⚠️")
    elif data == "instructions":
        await query.answer(texts.INSTRUCTIONS, show_alert=True)
    elif data == "trial":
        await _trial(query)
    elif data.startswith("menu#"):
        await _menu(client, query, data.split("#", 1)[1])
    elif data.startswith("settings#"):
        await _toggle_setting(client, query, data)
    elif data.startswith("nav#"):
        await _nav(client, query, data)
    elif data.startswith("navf#"):
        await _nav_filtered(client, query, data)
    elif data.startswith("filtermenu#"):
        await _filter_menu(query, data)
    elif data.startswith("filter#"):
        await _apply_filter(client, query, data)
    elif data.startswith("sendall#"):
        await _send_all(client, query, data)
    elif data.startswith("file#"):
        await _open_file(client, query, data)
    elif data.startswith("regain#"):
        await _regain(query, data)
    elif data.startswith("stream#"):
        await _stream(client, query, data)
    elif data.startswith("checksub#"):
        await _check_sub(client, query, data)
    elif data.startswith("suggest#"):
        await _suggest(client, query, data)


# ------------------------------------------------------------------- close
async def _close(query) -> None:
    await query.answer(texts.CLOSED)
    replied = query.message.reply_to_message
    try:
        await query.message.delete()
    except Exception:  # noqa: BLE001
        pass
    if replied is not None:
        try:
            await replied.delete()
        except Exception:  # noqa: BLE001
            pass


# -------------------------------------------------------------------- menus
async def _menu(client: Client, query, name: str) -> None:
    if name == "start":
        await _edit(
            query,
            texts.START_TEXT.format(
                mention=query.from_user.mention, wish=texts.greeting()
            ),
            kb.start_keyboard(),
        )
    elif name == "about":
        await _edit(
            query,
            texts.ABOUT_TEXT.format(
                bot_name=state.bot_name or "Auto Filter",
                stream_status="on" if settings.media_enabled() else "off",
            ),
            kb.about_keyboard(),
        )
    elif name == "help":
        await _edit(query, texts.HELP_TEXT, kb.help_keyboard())
    elif name == "user_cmd":
        await _edit(query, texts.USER_COMMANDS, kb.back_keyboard("menu#help"))
    elif name == "admin_cmd":
        if not settings.is_admin(query.from_user.id):
            await query.answer(texts.ADMIN_ONLY_BUTTON, show_alert=True)
            return
        await _edit(query, texts.ADMIN_COMMANDS, kb.back_keyboard("menu#help"))
    elif name == "plans":
        await _edit(query, texts.PLANS.format(upi=settings.owner_upi), kb.plans_keyboard())
    elif name == "stats":
        from services import stats

        if not settings.is_admin(query.from_user.id):
            await query.answer(texts.ADMIN_ONLY_BUTTON, show_alert=True)
            return
        snap = await stats.snapshot()
        await _edit(query, stats.text(snap), kb.back_keyboard("menu#about"))
    else:
        await query.answer()


async def _trial(query) -> None:
    if await premium.start_trial(query.from_user.id):
        await _edit(query, texts.TRIAL_GRANTED)
    else:
        await _edit(query, texts.TRIAL_USED)


# ----------------------------------------------------------------- settings
async def _toggle_setting(client: Client, query, data: str) -> None:
    try:
        _, key, chat_id = data.split("#", 2)
        chat_id = int(chat_id)
    except ValueError:
        await query.answer(texts.SOMETHING_WRONG, show_alert=True)
        return

    if not await is_chat_admin(client, chat_id, query.from_user.id):
        await query.answer("This is not for you!", show_alert=True)
        return

    current = await get_settings(chat_id)
    if not isinstance(current.get(key), bool):
        await query.answer(texts.SOMETHING_WRONG, show_alert=True)
        return

    value = not current[key]
    updated = await update_setting(chat_id, key, value)
    try:
        await query.message.edit_reply_markup(kb.settings_keyboard(updated, chat_id))
    except MessageNotModified:
        pass
    await query.answer("✅ enabled" if value else "❌ disabled")


# ---------------------------------------------------------------- pagination
async def _nav(client: Client, query, data: str) -> None:
    try:
        _, key, req, offset = data.split("#")
    except ValueError:
        await query.answer(texts.SOMETHING_WRONG, show_alert=True)
        return
    if not _viewer_ok(query, req):
        await query.answer(texts.NOT_FOR_YOU.format(name=query.from_user.first_name), show_alert=True)
        return
    session = state.search_cache.get(key)
    if session is None:
        await query.answer(texts.SEARCH_EXPIRED, show_alert=True)
        return

    page = await render.render_page(
        session, viewer_id=query.from_user.id, offset=_int(offset)
    )
    await _edit(query, page.text, page.keyboard)


async def _nav_filtered(client: Client, query, data: str) -> None:
    try:
        _, kind, value, key, req, offset = data.split("#")
    except ValueError:
        await query.answer(texts.SOMETHING_WRONG, show_alert=True)
        return
    if not _viewer_ok(query, req):
        await query.answer(texts.NOT_FOR_YOU.format(name=query.from_user.first_name), show_alert=True)
        return
    session = state.search_cache.get(key)
    if session is None:
        await query.answer(texts.SEARCH_EXPIRED, show_alert=True)
        return

    lang = value if kind == "lang" else ""
    quality = value if kind == "qual" else ""
    page = await render.render_page(
        session,
        viewer_id=query.from_user.id,
        offset=_int(offset),
        lang=lang,
        quality=quality,
    )
    await _edit(query, page.text, page.keyboard)


async def _filter_menu(query, data: str) -> None:
    try:
        _, kind, key, req, offset = data.split("#")
    except ValueError:
        await query.answer(texts.SOMETHING_WRONG, show_alert=True)
        return
    if not _viewer_ok(query, req):
        await query.answer(texts.NOT_FOR_YOU.format(name=query.from_user.first_name), show_alert=True)
        return
    if state.search_cache.get(key) is None:
        await query.answer(texts.SEARCH_EXPIRED, show_alert=True)
        return

    values = settings.languages if kind == "lang" else settings.quality
    title = "language" if kind == "lang" else "quality"
    await _edit(
        query,
        f"<b>Which {title} do you want? Pick one 👇</b>",
        kb.filter_menu_keyboard(kind, tuple(values), key, _int(req), _int(offset)),
    )


async def _apply_filter(client: Client, query, data: str) -> None:
    try:
        _, kind, value, key, req, offset = data.split("#")
    except ValueError:
        await query.answer(texts.SOMETHING_WRONG, show_alert=True)
        return
    if not _viewer_ok(query, req):
        await query.answer(texts.NOT_FOR_YOU.format(name=query.from_user.first_name), show_alert=True)
        return
    session = state.search_cache.get(key)
    if session is None:
        await query.answer(texts.SEARCH_EXPIRED, show_alert=True)
        return

    lang = value if kind == "lang" else ""
    quality = value if kind == "qual" else ""
    page = await render.render_page(
        session, viewer_id=query.from_user.id, offset=0, lang=lang, quality=quality
    )
    if not page.files:
        await query.answer(f"Sorry, no {value} files were found 😕", show_alert=True)
        return
    await _edit(query, page.text, page.keyboard)


async def _send_all(client: Client, query, data: str) -> None:
    try:
        _, key, req = data.split("#")
    except ValueError:
        await query.answer(texts.SOMETHING_WRONG, show_alert=True)
        return
    if not _viewer_ok(query, req):
        await query.answer(texts.NOT_FOR_YOU.format(name=query.from_user.first_name), show_alert=True)
        return
    session = state.search_cache.get(key)
    if session is None:
        await query.answer(texts.SEARCH_EXPIRED, show_alert=True)
        return
    await _open_link(query, f"all_{session.chat_id}_{session.key}")


# ------------------------------------------------------------------- files
async def _open_file(client: Client, query, data: str) -> None:
    try:
        _, file_id = data.split("#", 1)
    except ValueError:
        await query.answer(texts.SOMETHING_WRONG, show_alert=True)
        return
    await _open_link(query, f"file_{query.message.chat.id}_{file_id}")


async def _regain(query, data: str) -> None:
    try:
        _, kind, chat_id, token = data.split("#", 3)
    except ValueError:
        await query.answer(texts.SOMETHING_WRONG, show_alert=True)
        return
    payload = f"all_{chat_id}_{token}" if kind == "all" else f"file_{chat_id}_{token}"
    if not await _open_link(query, payload):
        return
    try:
        await query.message.delete()
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------- streaming
async def _stream(client: Client, query, data: str) -> None:
    file_id = data.split("#", 1)[1]
    message = await streaming.ensure_message(client, file_id)
    if message is None:
        await query.answer("This file cannot be streamed right now.", show_alert=True)
        return
    await query.answer()
    watch_url, download_url = streaming.urls(message.id)
    try:
        await query.message.edit_reply_markup(kb.watch_keyboard(watch_url, download_url))
    except MessageNotModified:
        pass


# --------------------------------------------------------------- force sub
async def _check_sub(client: Client, query, data: str) -> None:
    payload = data.split("#", 1)[1] if "#" in data else ""
    parsed = deeplink.parse(payload)
    gate = await gates.fsub_gate(client, parsed.group_id or 0, query.from_user.id, payload)
    if gate:
        _, markup = gate
        await query.answer("Please join the channel first.", show_alert=True)
        try:
            await query.message.edit_reply_markup(markup)
        except MessageNotModified:
            pass
        return

    if not payload:
        await query.answer()
        await query.message.edit_text(texts.VERIFIED.format(duration="now"))
        return
    if not await _open_link(query, payload):
        return
    try:
        await query.message.delete()
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------- suggest
async def _suggest(client: Client, query, data: str) -> None:
    try:
        _, movie_id, req = data.split("#", 2)
    except ValueError:
        await query.answer(texts.SOMETHING_WRONG, show_alert=True)
        return
    if not _viewer_ok(query, req):
        await query.answer(texts.NOT_FOR_YOU.format(name=query.from_user.first_name), show_alert=True)
        return

    title = await imdb.title_for_id(movie_id)
    if not title:
        await query.answer(texts.SOMETHING_WRONG, show_alert=True)
        return

    await query.answer()
    await _edit(query, texts.SEARCHING.format(query=html.escape(title)))
    chat_settings = await get_settings(query.message.chat.id)
    await search_flow.run_search(
        client,
        chat_id=query.message.chat.id,
        query=title,
        viewer=query.from_user,
        chat_title=query.message.chat.title or "Private chat",
        placeholder=query.message,
        chat_settings=chat_settings,
    )


__all__ = ["CALLBACK_RE", "on_callback"]
