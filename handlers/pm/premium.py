"""Premium plans and status for regular users."""

from __future__ import annotations

import logging

from pyrogram import Client, filters
from pyrogram.enums import ParseMode

from core.fmt import readable_time
from handlers.common import react, send_plans
from services import premium
from ui import keyboards as kb
from ui import texts

log = logging.getLogger(__name__)


@Client.on_message(filters.command("plan"), group=0)
async def plan_cmd(client: Client, message):
    await react(message)
    await send_plans(client, message.chat.id, message.id)


@Client.on_message(filters.command("myplan"), group=0)
async def myplan_cmd(client: Client, message):
    await react(message)
    user_id = message.from_user.id

    remaining = await premium.remaining(user_id)
    if remaining is None:
        await message.reply_text(texts.PREMIUM_NONE, reply_markup=kb.trial_keyboard())
        return

    expires = await premium.expires_at(user_id)
    await message.reply_text(
        texts.PREMIUM_ACTIVE.format(
            remaining=readable_time(remaining.total_seconds()),
            expires=expires.strftime("%Y-%m-%d %H:%M UTC") if expires else "-",
        ),
        parse_mode=ParseMode.HTML,
    )


__all__ = ["myplan_cmd", "plan_cmd"]
