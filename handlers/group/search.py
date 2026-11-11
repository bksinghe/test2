"""Auto filter inside groups, including the moderation extras.

Kept features from the original: ``@admin`` reports, link deletion, ``#request``
forwarding, the support group shortcut and the auto delete timer.
"""

from __future__ import annotations

import html
import logging
import re

from pyrogram import Client, filters
from pyrogram.enums import ChatMembersFilter, ChatMemberStatus, ParseMode
from pyrogram.types import InlineKeyboardMarkup

from config import settings
from filters.guards import chat_enabled, not_banned, not_command
from services import delivery
from services.registry import ensure_chat
from services.rights import is_bot_admin, is_chat_admin
from services.search_flow import run_search
from services.settings import get_settings
from ui import keyboards as kb
from ui import texts

log = logging.getLogger(__name__)

SEARCH_GROUP = 10
LINK_RE = re.compile(r"https?://\S+|www\.\S+|t\.me/\S+|@\w+", re.IGNORECASE)
MENTION_RE = re.compile(r"@admins?\b", re.IGNORECASE)
REQUEST_TAG = "#request"
REQUEST_TAG_RE = re.compile(r"#request", re.IGNORECASE)


@Client.on_message(
    filters.group & filters.text & not_command & not_banned & chat_enabled & filters.incoming,
    group=SEARCH_GROUP,
)
async def group_search(client: Client, message):
    if not await _bot_can_work(client, message):
        return

    await ensure_chat(client, message.chat, members=getattr(message.chat, "members_count", None))
    chat_settings = await get_settings(message.chat.id)

    if not chat_settings["auto_filter"]:
        await _auto_filter_off(client, message)
        return

    if message.from_user is None:
        await message.reply_text("I do not work for anonymous admins.")
        return

    text = message.text or ""

    if settings.support_group and message.chat.id == settings.support_group:
        total = await search_flow_count(text)
        await message.reply_text(
            f"Total <b>{total}</b> results found in this group",
            reply_markup=InlineKeyboardMarkup([[kb.button("Here", url=settings.films_link)]]),
        )
        return

    if MENTION_RE.search(text):
        await _report_to_admins(client, message)
        return

    if LINK_RE.search(text) and not await is_chat_admin(client, message.chat.id, message.from_user.id):
        try:
            await message.delete()
        except Exception as error:  # noqa: BLE001
            log.debug("could not delete a link message: %s", error)
        await message.reply_text(texts.LINK_BLOCKED)
        return

    if REQUEST_TAG in text.lower() and not is_bot_admin(message.from_user.id):
        await _forward_request(client, message, text)
        return

    placeholder = await message.reply_text(
        texts.SEARCHING.format(query=html.escape(text[:64]))
    )
    result = await run_search(
        client,
        chat_id=message.chat.id,
        query=text,
        viewer=message.from_user,
        chat_title=message.chat.title or "",
        placeholder=placeholder,
        reply_to_id=message.id,
        chat_settings=chat_settings,
    )
    if result is not None and chat_settings["auto_delete"]:
        delivery.schedule_group_delete(
            client,
            chat_id=message.chat.id,
            message_id=result.id,
            source_message_id=message.id,
        )


async def search_flow_count(text: str) -> int:
    from services import search as search_service

    return await search_service.count(text)


async def _bot_can_work(client: Client, message) -> bool:
    """Only answer in groups where the bot is an admin (as before)."""
    try:
        me = await client.get_me()
        member = await client.get_chat_member(message.chat.id, me.id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception as error:  # noqa: BLE001 - not a member / no access
        log.debug("bot is not an admin in %s: %s", message.chat.id, error)
        return False


async def _auto_filter_off(client: Client, message) -> None:
    warning = await message.reply_text(texts.AUTO_FILTER_OFF)
    delivery.schedule_cleanup(
        client, chat_id=message.chat.id, message_ids=[warning.id, message.id], delay=5
    )


async def _report_to_admins(client: Client, message) -> None:
    if await is_chat_admin(client, message.chat.id, message.from_user.id):
        return

    admins: list[int] = []
    try:
        async for member in client.get_chat_members(
            chat_id=message.chat.id, filter=ChatMembersFilter.ADMINISTRATORS
        ):
            if member.user.is_bot:
                continue
            admins.append(member.user.id)
            source = message.reply_to_message or message
            try:
                link = _message_link(source)
                forwarded = await source.forward(member.user.id)
                await forwarded.reply_text(
                    f"#Attention\n★ User: {message.from_user.mention}\n"
                    f"★ Group: {message.chat.title}\n\n"
                    + (f"★ <a href={link}>Go to message</a>" if link else ""),
                    disable_web_page_preview=True,
                )
            except Exception as error:  # noqa: BLE001 - admin may block the bot
                log.debug("could not report to %s: %s", member.user.id, error)
    except Exception as error:  # noqa: BLE001
        log.warning("could not list admins of %s: %s", message.chat.id, error)

    hidden = "".join(f"[\u2064](tg://user?id={admin})" for admin in admins)
    await message.reply_text(
        texts.REPORT_SENT + hidden,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )


def _message_link(message) -> str:
    """``Message.link`` raises for private groups, so never let it bubble up."""
    try:
        return message.link or ""
    except ValueError:
        return ""


async def _forward_request(client: Client, message, text: str) -> None:
    if settings.log_channel:
        try:
            await client.send_message(
                settings.log_channel,
                f"#Request\n★ User: {message.from_user.mention}\n"
                f"★ Group: {message.chat.title}\n\n"
                f"★ Message: {REQUEST_TAG_RE.sub('', text).strip()}",
            )
        except Exception as error:  # noqa: BLE001
            log.warning("could not forward the request: %s", error)
    await message.reply_text(texts.REQUEST_SENT)


__all__ = ["group_search"]
