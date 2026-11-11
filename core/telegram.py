"""Telegram call helpers with the boring failure modes handled.

Telegram answers a lot of perfectly normal situations with an error, and every
one of them used to become an unhandled exception inside a handler:

===============  =====================================================
``MessageIdInvalid``     the message is too old to edit
``MessageNotModified``   same content again
``MessageEmpty``         message was deleted meanwhile
``QueryIdInvalid``       the callback button was pressed twice / too late
``UserIsBlocked``        the user blocked the bot after pressing start
``ChatWriteForbidden``   bot was kicked or muted
===============  =====================================================

Everything user facing goes through :func:`safe_edit`, :func:`safe_send`,
:func:`safe_answer` and :func:`safe_react` so a dead button or a blocked user
can never crash a handler. The originating pyrogram object already carries its
client, so call sites stay short::

    await safe_edit(query.message, page.text, page.keyboard)
    await safe_answer(query, "Closed!")
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from pyrogram.enums import ParseMode
from pyrogram.errors import (
    ChannelInvalid,
    ChatAdminRequired,
    ChatWriteForbidden,
    InputUserDeactivated,
    MessageAuthorRequired,
    MessageEmpty,
    MessageIdInvalid,
    MessageNotModified,
    PeerIdInvalid,
    QueryIdInvalid,
    UserIsBlocked,
)
from pyrogram.types import Message

log = logging.getLogger(__name__)

MAX_TEXT = 4096

#: the message cannot be edited any more; a fresh message is the only option
EDIT_IMPOSSIBLE = (MessageIdInvalid, MessageEmpty, MessageAuthorRequired, ChannelInvalid)
#: the peer will never accept messages from us
SEND_IMPOSSIBLE = (
    UserIsBlocked,
    ChatWriteForbidden,
    PeerIdInvalid,
    InputUserDeactivated,
    ChannelInvalid,
    ChatAdminRequired,
)


def clip(text: str, limit: int = MAX_TEXT) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _client_of(target):
    client = getattr(target, "_client", None)
    if client is None:
        log.warning("no client available for %r", type(target).__name__)
    return client


async def safe_send(
    chat_id: int,
    text: str,
    markup=None,
    *,
    client=None,
    reply_to: int | None = None,
    parse_mode: ParseMode = ParseMode.HTML,
    protect_content: bool = False,
) -> Message | None:
    """Send a message, returning ``None`` instead of raising for dead peers."""
    if client is None:
        log.warning("safe_send called without a client")
        return None
    try:
        return await client.send_message(
            chat_id=chat_id,
            text=clip(text),
            reply_markup=markup,
            parse_mode=parse_mode,
            disable_web_page_preview=True,
            reply_to_message_id=reply_to,
            protect_content=protect_content,
        )
    except SEND_IMPOSSIBLE as error:
        log.debug("cannot message %s: %s", chat_id, error)
    except Exception as error:  # noqa: BLE001 - a send must never kill a handler
        log.warning("send to %s failed: %s", chat_id, error)
    return None


async def safe_edit(
    message: Message,
    text: str,
    markup=None,
    *,
    client=None,
    parse_mode: ParseMode = ParseMode.HTML,
) -> bool:
    """Edit a text message or a caption, falling back to a new message.

    Returns ``True`` when the message on screen shows ``text``.
    """
    text = clip(text)
    try:
        if getattr(message, "photo", None) or getattr(message, "video", None):
            await message.edit_caption(
                caption=text, reply_markup=markup, parse_mode=parse_mode
            )
        else:
            await message.edit_text(
                text,
                reply_markup=markup,
                disable_web_page_preview=True,
                parse_mode=parse_mode,
            )
        return True
    except MessageNotModified:
        return True
    except EDIT_IMPOSSIBLE as error:
        log.debug("editing %s is impossible (%s), sending a new message", message.id, error)
    except Exception as error:  # noqa: BLE001
        log.warning("edit of %s failed: %s", getattr(message, "id", "?"), error)
        return False

    client = client or _client_of(message)
    chat = getattr(message, "chat", None)
    if client is None or chat is None:
        return False
    await safe_delete(message, client=client)
    return await safe_send(chat.id, text, markup, client=client, parse_mode=parse_mode) is not None


async def safe_edit_markup(message: Message, markup=None) -> bool:
    """Swap only the keyboard (the usual settings toggle path)."""
    try:
        await message.edit_reply_markup(reply_markup=markup)
        return True
    except MessageNotModified:
        return True
    except EDIT_IMPOSSIBLE as error:
        log.debug("keyboard of %s cannot be edited: %s", getattr(message, "id", "?"), error)
    except Exception as error:  # noqa: BLE001
        log.warning("keyboard edit failed: %s", error)
    return False


async def safe_answer(
    query,
    text: str | None = None,
    *,
    show_alert: bool = False,
    url: str | None = None,
    cache_time: int = 0,
) -> bool:
    """Answer a callback query; a stale query id is not an error for us."""
    try:
        await query.answer(text, show_alert=show_alert, url=url, cache_time=cache_time)
        return True
    except QueryIdInvalid:
        log.debug("callback query %s is too old to answer", getattr(query, "id", "?"))
    except Exception as error:  # noqa: BLE001
        log.warning("could not answer a callback query: %s", error)
    return False


async def safe_inline_answer(query, *args, **kwargs) -> bool:
    """Answer an ``InlineQuery``; ``query.answer`` there takes results, not text."""
    try:
        await query.answer(*args, **kwargs)
        return True
    except QueryIdInvalid:
        log.debug("inline query %s expired", getattr(query, "id", "?"))
    except Exception as error:  # noqa: BLE001
        log.warning("could not answer an inline query: %s", error)
    return False


async def safe_delete(message: Message, *, client=None) -> None:
    client = client or _client_of(message)
    chat = getattr(message, "chat", None)
    if client is None or chat is None:
        return
    try:
        await client.delete_messages(chat_id=chat.id, message_ids=message.id)
    except Exception:  # noqa: BLE001 - deleting is always best effort
        pass


async def safe_react(message: Message, emojis: Iterable[str]) -> None:
    """React to a message; old messages and disabled reactions are ignored."""
    for emoji in emojis:
        try:
            await message.react(emoji=emoji, big=True)
            return
        except MessageIdInvalid:
            log.debug("cannot react to %s, it is too old", getattr(message, "id", "?"))
            return
        except Exception:  # noqa: BLE001 - reactions are cosmetic
            continue


__all__ = [
    "EDIT_IMPOSSIBLE",
    "MAX_TEXT",
    "SEND_IMPOSSIBLE",
    "clip",
    "safe_answer",
    "safe_delete",
    "safe_edit",
    "safe_edit_markup",
    "safe_inline_answer",
    "safe_react",
    "safe_send",
]
