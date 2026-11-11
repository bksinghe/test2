"""Bot admin utilities: stats, ping, id, speedtest, restart, eval, pm search."""

from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import sys
import time
import traceback
from io import StringIO

from pyrogram import Client, filters
from pyrogram.enums import ChatType, ParseMode
from pyrogram.errors import MessageTooLong

from config import settings
from core.fmt import human_size
from db import meta
from handlers.common import react
from services import stats
from services.rights import is_bot_admin
from ui import texts

log = logging.getLogger(__name__)

ADMIN_GROUP = 0
RESTART_FILE = "restart.txt"


def _admin_only(message) -> bool:
    return is_bot_admin(message.from_user.id if message.from_user else None)


@Client.on_message(filters.command("stats"), group=ADMIN_GROUP)
async def stats_cmd(client: Client, message):
    await react(message)
    if not _admin_only(message):
        await message.reply_text(texts.NOT_ADMIN)
        return
    snap = await stats.snapshot()
    await message.reply_text(stats.text(snap), parse_mode=ParseMode.HTML)


@Client.on_message(filters.command("ping"), group=ADMIN_GROUP)
async def ping_cmd(client: Client, message):
    # BUGFIX: the old code called ``time.monotonic`` on the ``time`` function.
    started = time.perf_counter()
    reply = await message.reply_text("👀")
    latency = (time.perf_counter() - started) * 1000
    await reply.edit_text(texts.PING.format(latency=f"{latency:.2f}"), parse_mode=ParseMode.HTML)


@Client.on_message(filters.command("id"), group=ADMIN_GROUP)
async def id_cmd(client: Client, message):
    # BUGFIX: used to crash on ``bool(...).chat``.
    replied = message.reply_to_message
    if replied is not None:
        if replied.forward_from_chat is not None:
            chat = replied.forward_from_chat
            await message.reply_text(
                f"Forwarded from <b>{chat.title}</b>\nID: <code>{chat.id}</code>",
                parse_mode=ParseMode.HTML,
            )
            return
        if replied.from_user is not None:
            user = replied.from_user
            await message.reply_text(
                f"👤 <b>{user.first_name}</b>\nID: <code>{user.id}</code>",
                parse_mode=ParseMode.HTML,
            )
            return

    if message.chat.type == ChatType.PRIVATE:
        await message.reply_text(f"👤 Your ID: <code>{message.from_user.id}</code>")
    elif message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        await message.reply_text(
            f"👫 Group ID: <code>{message.chat.id}</code>\n"
            f"👤 Your ID: <code>{message.from_user.id}</code>"
        )
    else:
        await message.reply_text(f"📣 Channel ID: <code>{message.chat.id}</code>")


@Client.on_message(filters.command("speedtest"), group=ADMIN_GROUP)
async def speedtest_cmd(client: Client, message):
    if not _admin_only(message):
        await message.reply_text(texts.NOT_ADMIN)
        return
    status = await message.reply_text("Initiating speedtest…")
    try:
        result = await asyncio.to_thread(_speedtest_sync)
    except Exception as error:  # noqa: BLE001 - network dependent
        await status.edit_text(f"Speedtest failed: <code>{error}</code>")
        return
    await message.reply_photo(photo=result["share"], caption=result["text"], parse_mode=ParseMode.HTML)
    await status.delete()


def _speedtest_sync() -> dict[str, str]:
    from speedtest import ConfigRetrievalError, Speedtest

    try:
        speed = Speedtest()
    except ConfigRetrievalError as error:  # pragma: no cover - network dependent
        raise RuntimeError("cannot reach a speedtest server") from error

    speed.get_best_server()
    speed.download()
    speed.upload()
    speed.results.share()
    data = speed.results.dict()
    text = (
        "<b>SPEEDTEST</b>\n"
        f"Upload: <code>{human_size(data['upload'])}/s</code>\n"
        f"Download: <code>{human_size(data['download'])}/s</code>\n"
        f"Ping: <code>{data['ping']} ms</code>\n"
        f"Server: <code>{data['server']['name']} ({data['server']['country']})</code>\n"
        f"ISP: <code>{data['client']['isp']}</code>"
    )
    return {"share": data["share"], "text": text}


@Client.on_message(filters.command("restart"), group=ADMIN_GROUP)
async def restart_cmd(client: Client, message):
    if not _admin_only(message):
        await message.reply_text(texts.NOT_ADMIN)
        return
    notice = await message.reply_text("Restarting…")
    with open(RESTART_FILE, "w", encoding="utf-8") as handle:
        json.dump({"chat_id": notice.chat.id, "message_id": notice.id}, handle)
    os.execl(sys.executable, sys.executable, *sys.argv)


@Client.on_message(filters.command("index_channels"), group=ADMIN_GROUP)
async def index_channels_cmd(client: Client, message):
    if not _admin_only(message):
        await message.reply_text(texts.NOT_ADMIN)
        return
    if not settings.index_channels:
        await message.reply_text("INDEX_CHANNELS is not configured.")
        return
    titles: list[str] = []
    for channel in settings.index_channels:
        try:
            chat = await client.get_chat(channel)
            titles.append(f"• {chat.title}")
        except Exception as error:  # noqa: BLE001
            titles.append(f"• <code>{channel}</code> (unavailable: {error})")
    await message.reply_text(
        "<b>Indexed channels</b>\n\n" + "\n".join(titles) + f"\n\n<b>Total:</b> {len(titles)}",
        parse_mode=ParseMode.HTML,
    )


@Client.on_message(filters.command("set_pm_search") & filters.private, group=ADMIN_GROUP)
async def set_pm_search_cmd(client: Client, message):
    await react(message)
    if not _admin_only(message):
        await message.reply_text(texts.NOT_ADMIN)
        return
    parts = (message.text or "").split(maxsplit=1)
    option = parts[1].strip().lower() if len(parts) > 1 else ""
    if option in {"on", "true", "yes", "1", "enable"}:
        await meta.set_pm_search(True)
        await message.reply_text(texts.PM_SEARCH_ON)
    elif option in {"off", "false", "no", "0", "disable"}:
        await meta.set_pm_search(False)
        await message.reply_text(texts.PM_SEARCH_OFF)
    else:
        await message.reply_text(texts.PM_SEARCH_INVALID)


@Client.on_message(filters.command("eval"), group=ADMIN_GROUP)
async def eval_cmd(client: Client, message):
    if not _admin_only(message):
        await message.reply_text(texts.NOT_ADMIN)
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text(texts.COMMAND_INCOMPLETE.format(usage="/eval print(1)"))
        return

    stdout, stderr = sys.stdout, sys.stderr
    captured_out, captured_err = StringIO(), StringIO()
    sys.stdout, sys.stderr = captured_out, captured_err
    error = ""
    try:
        await _exec(parts[1], client, message)
    except Exception:  # noqa: BLE001 - this is an eval helper by design
        error = traceback.format_exc()
    finally:
        sys.stdout, sys.stderr = stdout, stderr

    output = error or captured_err.getvalue() or captured_out.getvalue() or "Success!"
    body = f"<b>Output</b>\n<pre>{html.escape(output)[:3800]}</pre>"
    try:
        await message.reply_text(body, parse_mode=ParseMode.HTML)
    except MessageTooLong:
        path = "eval_output.txt"
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(output)
        await message.reply_document(path)
        os.remove(path)


async def _exec(code: str, client: Client, message) -> None:
    """Execute ``code`` with ``client`` and ``message`` in scope (await supported)."""
    source = "async def __aexec(client, message):\n" + "".join(
        f"    {line}\n" for line in code.splitlines() or [""]
    )
    scope: dict[str, object] = {"client": client, "message": message}
    exec(compile(source, "<eval>", "exec"), scope)  # noqa: S102 - admin only feature
    await scope["__aexec"](client, message)  # type: ignore[operator]


__all__ = [
    "eval_cmd",
    "id_cmd",
    "index_channels_cmd",
    "ping_cmd",
    "restart_cmd",
    "set_pm_search_cmd",
    "speedtest_cmd",
    "stats_cmd",
]
