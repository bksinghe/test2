"""Bot admin moderation: user bans, disabling groups, leaving, invite links."""

from __future__ import annotations

import logging

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup

from config import settings
from core import state
from db import chats as chats_db
from db import users as users_db
from handlers.common import react
from services.rights import is_bot_admin
from ui import keyboards as kb
from ui import texts

log = logging.getLogger(__name__)

ADMIN_GROUP = 0


def _parse(message, usage: str) -> tuple[str, str] | None:
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        return None
    target = parts[1].strip()
    reason = parts[2].strip() if len(parts) > 2 else "No reason provided"
    return target, reason


def _support_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[kb.button("Support group", url=settings.support_link)]])


@Client.on_message(filters.command("ban_user"), group=ADMIN_GROUP)
async def ban_user_cmd(client: Client, message):
    await react(message)
    if not is_bot_admin(message.from_user.id if message.from_user else None):
        await message.reply_text(texts.NOT_ADMIN)
        return
    parsed = _parse(message, texts.USAGE_CHAT_ID.format(command="ban_user"))
    if parsed is None:
        await message.reply_text(texts.COMMAND_INCOMPLETE.format(usage="/ban_user &lt;id&gt; [reason]"))
        return
    target, reason = parsed
    try:
        user = await client.get_users(int(target) if target.lstrip("-").isdigit() else target)
    except Exception as error:  # noqa: BLE001
        await message.reply_text(f"Cannot resolve that user: {error}")
        return
    if is_bot_admin(user.id):
        await message.reply_text("That user is a bot admin.")
        return

    status = await users_db.ban_status(user.id)
    if status.get("is_banned"):
        await message.reply_text(
            f"{user.mention} is already banned.\nReason - <code>{status.get('reason')}</code>"
        )
        return

    await users_db.set_ban(user.id, reason)
    state.banned_users.add(user.id)
    await message.reply_text(texts.USER_BANNED.format(mention=user.mention), parse_mode=ParseMode.HTML)
    try:
        await client.send_message(
            user.id,
            texts.BANNED_NOTICE.format(mention=user.mention, reason=reason),
            reply_markup=_support_markup(),
        )
    except Exception:  # noqa: BLE001
        pass


@Client.on_message(filters.command("unban_user"), group=ADMIN_GROUP)
async def unban_user_cmd(client: Client, message):
    await react(message)
    if not is_bot_admin(message.from_user.id if message.from_user else None):
        await message.reply_text(texts.NOT_ADMIN)
        return
    parsed = _parse(message, "")
    if parsed is None:
        await message.reply_text(texts.COMMAND_INCOMPLETE.format(usage="/unban_user &lt;id&gt;"))
        return
    target, _ = parsed
    try:
        user = await client.get_users(int(target) if target.lstrip("-").isdigit() else target)
    except Exception as error:  # noqa: BLE001
        await message.reply_text(f"Cannot resolve that user: {error}")
        return

    status = await users_db.ban_status(user.id)
    if not status.get("is_banned"):
        await message.reply_text(f"{user.mention} is not banned.")
        return

    await users_db.clear_ban(user.id)
    state.banned_users.discard(user.id)
    await message.reply_text(
        texts.USER_UNBANNED.format(mention=user.mention), parse_mode=ParseMode.HTML
    )


@Client.on_message(filters.command("ban_grp"), group=ADMIN_GROUP)
async def ban_group_cmd(client: Client, message):
    await react(message)
    if not is_bot_admin(message.from_user.id if message.from_user else None):
        await message.reply_text(texts.NOT_ADMIN)
        return
    parsed = _parse(message, "")
    if parsed is None:
        await message.reply_text(texts.COMMAND_INCOMPLETE.format(usage="/ban_grp &lt;chat_id&gt; [reason]"))
        return
    target, reason = parsed
    if not target.lstrip("-").isdigit():
        await message.reply_text(texts.INVALID_ID)
        return

    chat_id = int(target)
    status = await chats_db.status(chat_id)
    if status.get("is_disabled"):
        await message.reply_text(texts.CHAT_DISABLED.format(reason=status.get("reason") or "-"))
        return

    await chats_db.set_disabled(chat_id, True, reason)
    state.banned_chats.add(chat_id)
    await message.reply_text(texts.CHAT_DISABLED_OK)
    try:
        await client.send_message(
            chat_id,
            texts.LEFT_NOTICE.format(reason=reason),
            reply_markup=_support_markup(),
        )
        await client.leave_chat(chat_id)
    except Exception as error:  # noqa: BLE001
        await message.reply_text(f"Disabled, but could not notify the group: {error}")


@Client.on_message(filters.command("unban_grp"), group=ADMIN_GROUP)
async def unban_group_cmd(client: Client, message):
    if not is_bot_admin(message.from_user.id if message.from_user else None):
        await message.reply_text(texts.NOT_ADMIN)
        return
    parsed = _parse(message, "")
    if parsed is None or not parsed[0].lstrip("-").isdigit():
        await message.reply_text(texts.INVALID_ID)
        return
    chat_id = int(parsed[0])
    status = await chats_db.status(chat_id)
    if not status.get("is_disabled"):
        await message.reply_text("This chat is not disabled.")
        return
    await chats_db.set_disabled(chat_id, False)
    state.banned_chats.discard(chat_id)
    await message.reply_text(texts.CHAT_ENABLED)


@Client.on_message(filters.command("leave"), group=ADMIN_GROUP)
async def leave_cmd(client: Client, message):
    if not is_bot_admin(message.from_user.id if message.from_user else None):
        await message.reply_text(texts.NOT_ADMIN)
        return
    parsed = _parse(message, "")
    if parsed is None or not parsed[0].lstrip("-").isdigit():
        await message.reply_text(texts.COMMAND_INCOMPLETE.format(usage=texts.USAGE_LEAVE))
        return
    chat_id, reason = int(parsed[0]), parsed[1]
    try:
        await client.send_message(
            chat_id, texts.LEFT_NOTICE.format(reason=reason), reply_markup=_support_markup()
        )
        await client.leave_chat(chat_id)
    except Exception as error:  # noqa: BLE001
        await message.reply_text(f"Could not leave: {error}")
        return
    await message.reply_text(texts.LEFT_OK.format(chat_id=chat_id))


@Client.on_message(filters.command("invite_link"), group=ADMIN_GROUP)
async def invite_link_cmd(client: Client, message):
    if not is_bot_admin(message.from_user.id if message.from_user else None):
        await message.reply_text(texts.NOT_ADMIN)
        return
    parsed = _parse(message, "")
    if parsed is None or not parsed[0].lstrip("-").isdigit():
        await message.reply_text(texts.INVALID_ID)
        return
    try:
        link = await client.create_chat_invite_link(int(parsed[0]))
    except Exception as error:  # noqa: BLE001
        await message.reply_text(f"Could not create a link: {error}")
        return
    await message.reply_text(f"Invite link: {link.invite_link}")


__all__ = [
    "ban_group_cmd",
    "ban_user_cmd",
    "invite_link_cmd",
    "leave_cmd",
    "unban_group_cmd",
    "unban_user_cmd",
]
