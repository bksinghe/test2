"""Database dumps for bot admins (``/users`` and ``/chats``)."""

from __future__ import annotations

import os
import tempfile

from pyrogram import Client, filters

from core.telegram import safe_delete, safe_edit
from db import chats as chats_db
from db import users as users_db
from services.rights import is_bot_admin
from ui import texts

ADMIN_GROUP = 0
#: above this size the dump is sent as a .txt file instead of a message
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
    await _dump(client, message, status, lines, "users.txt")


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
    await _dump(client, message, status, lines, "chats.txt")


async def _dump(client: Client, message, status, lines: list[str], name: str) -> None:
    """Send the list as a message, or as a file once it gets too big."""
    rows = len(lines) - 1
    body = "\n".join(lines)
    if len(body) <= SEND_AS_FILE_AFTER:
        await safe_edit(status, body or "Nothing here yet.")
        return

    path = _write_temp(name, body)
    try:
        await client.send_document(
            chat_id=message.chat.id,
            document=path,
            file_name=name,
            caption=f"{rows} rows",
            reply_to_message_id=message.id,
        )
    finally:
        await safe_delete(status)
        try:
            os.remove(path)
        except OSError:
            pass


def _write_temp(name: str, body: str) -> str:
    path = os.path.join(tempfile.gettempdir(), f"{name}.{os.getpid()}.txt")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(body)
    return path


__all__ = ["chats_cmd", "users_cmd"]
