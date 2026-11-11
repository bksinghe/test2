"""Granting and revoking premium."""

from __future__ import annotations

import logging

from pyrogram import Client, filters
from pyrogram.enums import ParseMode

from core.clock import parse_duration
from core.fmt import readable_time
from db import users as users_db
from handlers.common import react
from services import premium
from services.rights import is_bot_admin
from ui import texts

log = logging.getLogger(__name__)

ADMIN_GROUP = 0


def _is_admin(message) -> bool:
    return is_bot_admin(message.from_user.id if message.from_user else None)


@Client.on_message(filters.command("add_premium"), group=ADMIN_GROUP)
async def add_premium_cmd(client: Client, message):
    await react(message)
    if not _is_admin(message):
        await message.reply_text(texts.NOT_ADMIN)
        return

    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.reply_text(
            texts.COMMAND_INCOMPLETE.format(usage="/add_premium &lt;user_id&gt; &lt;1day&gt;")
        )
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.reply_text("The user id must be a number.")
        return

    seconds = parse_duration(parts[2])
    if seconds is None:
        await message.reply_text(
            "Invalid duration. Use e.g. <code>1day</code>, <code>2hours</code>, "
            "<code>30min</code>, <code>1month</code>.",
            parse_mode=ParseMode.HTML,
        )
        return

    await users_db.add(user_id, str(user_id))
    until = await premium.grant(user_id, seconds)
    await message.reply_text(
        f"Premium granted to <code>{user_id}</code> until "
        f"<code>{until:%Y-%m-%d %H:%M} UTC</code>.",
        parse_mode=ParseMode.HTML,
    )
    try:
        await client.send_message(
            user_id,
            texts.PREMIUM_ADDED.format(duration=readable_time(seconds)),
            parse_mode=ParseMode.HTML,
        )
    except Exception as error:  # noqa: BLE001
        log.debug("could not notify %s: %s", user_id, error)


@Client.on_message(filters.command("remove_premium"), group=ADMIN_GROUP)
async def remove_premium_cmd(client: Client, message):
    await react(message)
    if not _is_admin(message):
        await message.reply_text(texts.NOT_ADMIN)
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.reply_text(
            texts.COMMAND_INCOMPLETE.format(usage="/remove_premium &lt;user_id&gt;")
        )
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.reply_text("The user id must be a number.")
        return

    await premium.revoke(user_id)
    await message.reply_text(f"Premium removed from <code>{user_id}</code>.")
    try:
        await client.send_message(
            user_id,
            texts.PREMIUM_REMOVED.format(owner="the support group"),
            parse_mode=ParseMode.HTML,
        )
    except Exception:  # noqa: BLE001
        pass


__all__ = ["add_premium_cmd", "remove_premium_cmd"]
