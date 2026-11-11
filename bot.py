"""Entrypoint.

Run with ``python bot.py``. All configuration comes from environment variables
(see ``.env.example``); nothing crashes at import time, and every configuration
problem is reported in one place before the bot connects.

Boot order matters: Pyrogram captures ``asyncio.get_event_loop()`` while it is
being **imported** (``pyrogram/sync.py``), and uvloop's policy raises instead of
creating a loop on demand. Creating and installing the loop first, importing
pyrogram second, is what avoids::

    RuntimeError: There is no current event loop in thread 'MainThread'
"""

from __future__ import annotations

import asyncio
import logging
import sys

from config import settings, warnings
from core.logging import setup

log = logging.getLogger("bot")


def _make_loop() -> asyncio.AbstractEventLoop:
    """Create the loop pyrogram will pick up, preferring uvloop when present."""
    try:
        import uvloop
    except ImportError:  # uvloop is optional (and unavailable on some platforms)
        log.info("uvloop not available, using the default asyncio loop")
        loop = asyncio.new_event_loop()
    else:
        uvloop.install()
        loop = uvloop.new_event_loop()
        log.info("using uvloop")
    asyncio.set_event_loop(loop)
    return loop


def main() -> int:
    setup()

    for warning in warnings():
        log.warning("config: %s", warning)

    problems = settings.validate()
    if problems:
        for problem in problems:
            log.error("config: %s", problem)
        print(
            "\nFix the environment variables above and start the bot again.\n"
            "A template is available in .env.example\n",
            file=sys.stderr,
        )
        return 1

    loop = _make_loop()

    # imported *after* the loop exists: pyrogram reads get_event_loop() on import
    from core.client import Bot

    log.info("starting with %s", settings.masked())
    bot = Bot()
    try:
        bot.run()
    except KeyboardInterrupt:
        log.info("interrupted, shutting down")
    finally:
        if not loop.is_closed():
            loop.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
