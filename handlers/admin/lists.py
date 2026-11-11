"""Database dumps for bot admins."""

from __future__ import annotations

import os

from pyrogram import Client, filters
from pyrogram.errors import MessageTooLong

from db import chats as chats_db
from db import users as users_db
from services.rights import is_bot_admin
from ui import texts

ADMIN_GROUP = 0
SEND_AS_FILE_AFTER = 3800


def _is_admin(message) -> bool:
    return is_bot_admin(message.from_user.id if message.from_user else None)


@Client.on_message(filters.command("users"), group=ADMIN_GROUP)
async def users_cmd(client: Client, message):
    if not _is_admin(message):
        await message.reply_text(texts.NOT_ADMIN)
        return

    status = await message.reply_text("Collecting users…")
    lines = ["<b>Users</b>\n"]
    async for user in users_db.all_users():
        flags = ""
        if (user.get("banned") or {}).get("is_banned"):
            flags += " (banned)"
        if (user.get("verify") or {}).get("verified"):
            flags += " (verified)"
        lines.append(f"<b>{user.get('name', '?')}</b> — <code>{user['id']}</code>{flags}")
    body = "\n".join(lines)

    try:
        await status.edit_text(body[:4000] or "No users yet.")
    except MessageTooLong:
        await status.delete()
        await message.reply_document(_write_temp("users.txt", body), caption="Users list")


@Client.on_message(filters.command("chats"), group=ADMIN_GROUP)
async def chats_cmd(client: Client, message):
    if not _is_admin(message):
        await message.reply_text(texts.NOT_ADMIN)
        return

    status = await message.reply_text("Collecting chats…")
    lines = ["<b>Chats</b>\n"]
    async for chat in chats_db.all_chats():
        disabled = " (disabled)" if (chat.get("disabled") or {}).get("is_disabled") else ""
        lines.append(f"<b>{chat.get('title', '?')}</b> — <code>{chat['id']}</code>{disabled}")
    body = "\n".join(lines)

    try:
        await status.edit_text(body[:4000] or "No chats yet.")
    except MessageTooLong:
        await status.delete()
        await message.reply_document(_write_temp("chats.txt", body), caption="Chats list")


def _write_temp(name: str, body: str) -> str:
    with open(name, "w", encoding="utf-8") as handle:
        handle.write(body)
    return name


async def cleanup(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


__all__ = ["chats_cmd", "cleanup", "users_cmd"]
