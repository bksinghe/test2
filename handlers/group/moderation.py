"""Group moderation: single user actions and the bulk cleanup menu."""

from __future__ import annotations

import logging

from pyrogram import Client, filters
from pyrogram.enums import ChatMembersFilter, ParseMode
from pyrogram.errors import ChatAdminRequired, UserAdminInvalid
from pyrogram.types import ChatPermissions

from handlers.common import group_admin_guard, react
from services.rights import is_chat_admin
from ui import keyboards as kb
from ui import texts

log = logging.getLogger(__name__)


async def _resolve_user(client: Client, message):
    """Return a user object for the replied message, id or username."""
    replied = message.reply_to_message
    if replied is not None and replied.from_user is not None:
        return replied.from_user

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return None
    target = parts[1].strip()
    try:
        user_id = int(target)
    except ValueError:
        user_id = target
    try:
        return await client.get_users(user_id)
    except Exception:  # noqa: BLE001 - user not found / hidden
        return None


@Client.on_message(filters.command("manage") & filters.group, group=0)
async def manage_cmd(client: Client, message):
    if not await group_admin_guard(client, message):
        return
    await message.reply_text(
        "Select a member management action.", reply_markup=kb.manage_keyboard()
    )


@Client.on_message(filters.command("ban") & filters.group, group=0)
async def ban_cmd(client: Client, message):
    await react(message)
    if not await group_admin_guard(client, message):
        return
    user = await _resolve_user(client, message)
    if user is None:
        await message.reply_text("Reply to a user or give an id/username.")
        return
    try:
        # BUGFIX: the original banned inside the admin's private chat.
        await client.ban_chat_member(message.chat.id, user.id)
    except (ChatAdminRequired, UserAdminInvalid) as error:
        await message.reply_text(f"I cannot ban this user: {error}")
        return
    await message.reply_text(
        f"Successfully banned {user.mention} from {message.chat.title}", parse_mode=ParseMode.HTML
    )


@Client.on_message(filters.command("mute") & filters.group, group=0)
async def mute_cmd(client: Client, message):
    await react(message)
    if not await group_admin_guard(client, message):
        return
    user = await _resolve_user(client, message)
    if user is None:
        await message.reply_text("Reply to a user or give an id/username.")
        return
    try:
        await client.restrict_chat_member(message.chat.id, user.id, ChatPermissions())
    except (ChatAdminRequired, UserAdminInvalid) as error:
        await message.reply_text(f"I cannot mute this user: {error}")
        return
    await message.reply_text(
        f"Successfully muted {user.mention} in {message.chat.title}", parse_mode=ParseMode.HTML
    )


@Client.on_message(filters.command(["unban", "unmute"]) & filters.group, group=0)
async def unban_cmd(client: Client, message):
    if not await group_admin_guard(client, message):
        return
    user = await _resolve_user(client, message)
    if user is None:
        await message.reply_text("Reply to a user or give an id/username.")
        return
    try:
        await client.unban_chat_member(message.chat.id, user.id)
    except (ChatAdminRequired, UserAdminInvalid) as error:
        await message.reply_text(f"I cannot {message.command[0]} this user: {error}")
        return
    await message.reply_text(
        f"Successfully {message.command[0]}ned {user.mention} in {message.chat.title}",
        parse_mode=ParseMode.HTML,
    )


# --------------------------------------------------------------- bulk menu
async def _collect(client: Client, chat_id: int, member_filter) -> list[int]:
    ids: list[int] = []
    async for member in client.get_chat_members(chat_id=chat_id, filter=member_filter):
        ids.append(member.user.id)
    return ids


async def _kick(client: Client, chat_id: int, user_id: int) -> None:
    """Ban+unban = kick (Pyrogram 2.x has no ``until_date`` argument)."""
    await client.ban_chat_member(chat_id, user_id)
    await client.unban_chat_member(chat_id, user_id)


@Client.on_callback_query(filters.regex(r"^mgmt#"), group=0)
async def manage_callback(client: Client, query):
    if not await is_chat_admin(client, query.message.chat.id, query.from_user.id):
        await query.answer(texts.ADMIN_ONLY_BUTTON, show_alert=True)
        return

    action = query.data.split("#", 1)[1]
    chat_id = query.message.chat.id
    await query.answer()
    await query.message.edit_text("Working on it, this can take a while…")

    try:
        if action == "unmute_all":
            targets = await _collect(client, chat_id, ChatMembersFilter.RESTRICTED)
            for user_id in targets:
                await client.unban_chat_member(chat_id, user_id)
            summary = f"Successfully unmuted <code>{len(targets)}</code> users."
        elif action == "unban_all":
            targets = await _collect(client, chat_id, ChatMembersFilter.BANNED)
            for user_id in targets:
                await client.unban_chat_member(chat_id, user_id)
            summary = f"Successfully unbanned <code>{len(targets)}</code> users."
        elif action == "kick_muted":
            targets = await _collect(client, chat_id, ChatMembersFilter.RESTRICTED)
            for user_id in targets:
                await _kick(client, chat_id, user_id)
            summary = f"Successfully kicked <code>{len(targets)}</code> muted users."
        elif action == "kick_deleted":
            targets = [
                member.user.id
                async for member in client.get_chat_members(chat_id)
                if member.user.is_deleted
            ]
            for user_id in targets:
                await _kick(client, chat_id, user_id)
            summary = f"Successfully kicked <code>{len(targets)}</code> deleted accounts."
        else:
            summary = texts.SOMETHING_WRONG
    except Exception as error:  # noqa: BLE001 - report and keep going
        log.warning("bulk action %s failed: %s", action, error)
        summary = f"Something went wrong:\n<code>{error}</code>"

    await query.message.edit_text(summary, parse_mode=ParseMode.HTML)


__all__ = ["ban_cmd", "manage_callback", "manage_cmd", "mute_cmd", "unban_cmd"]
