"""Entrypoint.

Run with ``python bot.py``. All configuration comes from environment variables
(see ``.env.example``); nothing crashes at import time, and every configuration
problem is reported in one place before the bot connects.
"""

from __future__ import annotations

import logging
import sys

import uvloop

from config import settings, warnings
from core.logging import setup

log = logging.getLogger("bot")


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

    uvloop.install()

    from core.client import Bot  # imported late so config errors print cleanly

    log.info("starting with %s", settings.masked())
    Bot().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
