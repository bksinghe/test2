"""Bot lifecycle: database checks, state bootstrap, web server, health checks."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time

from aiohttp import web
from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.errors import RPCError

from config import settings
from core import state
from db import chats, mongo, users

log = logging.getLogger(__name__)

RESTART_FILE = "restart.txt"


class Bot(Client):
    def __init__(self) -> None:
        super().__init__(
            name=settings.session_name,
            api_id=settings.api_id,
            api_hash=settings.api_hash,
            bot_token=settings.bot_token,
            workers=settings.workers,
            plugins={"root": "handlers"},
            sleep_threshold=30,
        )
        self._web_runner: web.AppRunner | None = None

    # ------------------------------------------------------------- startup
    async def start(self) -> Bot:
        state.START_TIME = time.time()
        _install_error_filter()

        if not await mongo.ping():
            raise RuntimeError(
                "cannot reach MongoDB - check DATABASE_URL (the bot refuses to run without it)"
            )
        await mongo.ensure_indexes()

        state.banned_users.update(await users.banned_ids())
        state.banned_chats.update(await chats.disabled_ids())

        await super().start()

        me = await self.get_me()
        state.bot = self
        state.me = me.id
        state.username = me.username
        state.bot_name = me.first_name
        log.info("connected as @%s (%s)", me.username, me.id)

        await self._finish_restart_notice()
        await self._start_web_server()
        await self._health_checks()
        return self

    async def stop(self, *args) -> None:
        log.info("shutting down…")
        if self._web_runner is not None:
            try:
                await self._web_runner.cleanup()
            except Exception as error:  # noqa: BLE001
                log.debug("web server cleanup failed: %s", error)
        await mongo.close()
        await super().stop()
        log.info("stopped")

    # ------------------------------------------------------------ internals
    async def _start_web_server(self) -> None:
        if not settings.media_enabled():
            log.warning("URL/BIN_CHANNEL missing - HTTP streaming is disabled")
            return
        from web.app import create_app

        self._web_runner = web.AppRunner(create_app())
        await self._web_runner.setup()
        site = web.TCPSite(self._web_runner, "0.0.0.0", settings.port)
        await site.start()
        log.info("streaming server listening on 0.0.0.0:%s", settings.port)

    async def _finish_restart_notice(self) -> None:
        if not os.path.exists(RESTART_FILE):
            return
        try:
            with open(RESTART_FILE, encoding="utf-8") as handle:
                data = json.load(handle)
            await self.edit_message_text(
                chat_id=data["chat_id"],
                message_id=data["message_id"],
                text="<b>✅ Restarted successfully!</b>",
                parse_mode=ParseMode.HTML,
            )
        except Exception as error:  # noqa: BLE001 - the message may be gone
            log.debug("could not edit the restart message: %s", error)
        finally:
            try:
                os.remove(RESTART_FILE)
            except OSError:
                pass

    async def _health_checks(self) -> None:
        """Warn (never exit) when the configured channels are not reachable."""
        if settings.log_channel:
            try:
                await self.send_message(
                    chat_id=settings.log_channel,
                    text=(
                        f"<b>🤖 {state.bot_name} is online</b>\n"
                        f"<i>@{state.username}</i>"
                    ),
                )
            except Exception as error:  # noqa: BLE001
                log.error("LOG_CHANNEL is not reachable (%s) - make the bot an admin", error)

        if settings.bin_channel:
            try:
                probe = await self.send_message(settings.bin_channel, "test")
                await probe.delete()
            except Exception as error:  # noqa: BLE001
                log.error("BIN_CHANNEL is not reachable (%s) - streaming will fail", error)

        for admin in settings.admins:
            try:
                await self.send_message(
                    chat_id=admin, text="<b>✅ Bot restarted</b>", parse_mode=ParseMode.HTML
                )
            except Exception:  # noqa: BLE001 - admin may have blocked the bot
                pass


def _install_error_filter() -> None:
    """Stop harmless Telegram errors from printing full tracebacks.

    Pyrogram runs every handler in its own task and does not catch exceptions,
    so an ``RPCError`` we did not anticipate (a message that is too old, a user
    that blocked the bot, a callback pressed twice) ended up as a scary
    "Task exception was never retrieved" traceback in the logs. The helpers in
    :mod:`core.telegram` handle the known ones; this is the last net for the
    rest - real bugs still get their full traceback.
    """
    loop = asyncio.get_running_loop()
    previous = loop.get_exception_handler()

    def handler(loop_, context) -> None:
        error = context.get("exception")
        if isinstance(error, RPCError):
            log.warning("telegram error ignored: %s", error)
            return
        if previous is not None:
            previous(loop_, context)
        else:
            loop_.default_exception_handler(context)

    loop.set_exception_handler(handler)


__all__ = ["Bot", "RESTART_FILE"]
