"""User and group broadcasts with progress and cancellation."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.errors import (
    ChatWriteForbidden,
    FloodWait,
    InputUserDeactivated,
    PeerIdInvalid,
    UserIsBlocked,
)
from pyrogram.types import Message

from core import state
from core.fmt import readable_time
from db import chats as chats_db
from db import users as users_db
from services.rights import is_bot_admin
from ui import keyboards as kb
from ui import texts

log = logging.getLogger(__name__)

ADMIN_GROUP = 0
PROGRESS_EVERY = 20

START_STATES = {"broadcast": ("users", False), "pin_broadcast": ("users", True),
                "grp_broadcast": ("groups", False), "pin_grp_broadcast": ("groups", True)}


@Client.on_message(
    filters.command(list(START_STATES)) & filters.reply, group=ADMIN_GROUP
)
async def broadcast_cmd(client: Client, message):
    if not is_bot_admin(message.from_user.id if message.from_user else None):
        await message.reply_text(texts.NOT_ADMIN)
        return
    if state.broadcast_lock.locked():
        await message.reply_text("Another broadcast is running, please wait.")
        return

    target, pin = START_STATES[message.command[0]]
    source = message.reply_to_message
    total = (
        await users_db.count() if target == "users" else await chats_db.count()
    )
    if total == 0:
        await message.reply_text("There is nobody to broadcast to.")
        return

    status = await message.reply_text(
        texts.BROADCAST_STARTED.format(target=target)
    )
    started = time.time()
    done = success = failed = 0

    async with state.broadcast_lock:
        state.broadcast_cancel[target] = False
        async for chat_id in _targets(target):
            if state.broadcast_cancel[target]:
                state.broadcast_cancel[target] = False
                await status.edit_text(texts.BROADCAST_CANCELLED)
                return

            try:
                sent = await _copy(client, source, chat_id, pin)
                success += 1 if sent else 0
            except FloodWait as wait:
                await asyncio.sleep(wait.value)
                try:
                    success += 1 if await _copy(client, source, chat_id, pin) else 0
                except Exception:  # noqa: BLE001
                    failed += 1
            except (UserIsBlocked, InputUserDeactivated):
                # only remove users that can never receive messages again
                await users_db.delete(chat_id)
                failed += 1
            except (PeerIdInvalid, ChatWriteForbidden) as error:
                log.debug("broadcast skipped %s: %s", chat_id, error)
                failed += 1
            except Exception as error:  # noqa: BLE001 - never lose data on hiccups
                log.debug("broadcast failed for %s: %s", chat_id, error)
                failed += 1

            done += 1
            if done % PROGRESS_EVERY == 0:
                try:
                    await status.edit_text(
                        texts.BROADCAST_PROGRESS.format(
                            target=target, done=done, total=total,
                            success=success, failed=failed,
                        ),
                        reply_markup=kb.broadcast_cancel_keyboard(target),
                        parse_mode=ParseMode.HTML,
                    )
                except Exception as error:  # noqa: BLE001
                    log.debug("broadcast progress update failed: %s", error)

    await status.edit_text(
        texts.BROADCAST_DONE.format(
            duration=readable_time(time.time() - started),
            target=target, done=done, total=total, success=success, failed=failed,
        ),
        parse_mode=ParseMode.HTML,
    )


async def _targets(target: str) -> AsyncIterator[int]:
    source = users_db.all_users() if target == "users" else chats_db.all_chats()
    async for item in source:
        yield int(item["id"])


async def _copy(client: Client, source: Message, chat_id: int, pin: bool) -> bool:
    sent = await source.copy(chat_id=chat_id)
    if pin and sent is not None:
        try:
            await sent.pin(both_sides=True)
        except Exception:  # noqa: BLE001 - pin may not be permitted
            pass
    return sent is not None


@Client.on_callback_query(filters.regex(r"^broadcast_cancel#"), group=ADMIN_GROUP)
async def broadcast_cancel(client: Client, query):
    if not is_bot_admin(query.from_user.id):
        await query.answer(texts.ADMIN_ONLY_BUTTON, show_alert=True)
        return
    target = query.data.split("#", 1)[1]
    if target in state.broadcast_cancel:
        state.broadcast_cancel[target] = True
    await query.answer("Stopping…")


__all__ = ["broadcast_cancel", "broadcast_cmd"]
