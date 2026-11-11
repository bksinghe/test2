"""Logging setup (the old code only used ``print``)."""

from __future__ import annotations

import logging
import os

FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-22s | %(message)s"


def setup() -> None:
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=level, format=FORMAT, datefmt="%H:%M:%S")
    for noisy in ("pyrogram", "pymongo", "motor", "aiohttp.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    logging.getLogger(__name__).info("logging initialised at %s", level)


__all__ = ["FORMAT", "setup"]
