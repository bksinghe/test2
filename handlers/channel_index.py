"""Auto index files posted in the configured ``INDEX_CHANNELS``."""

from __future__ import annotations

import logging

from pyrogram import Client, filters

from config import settings
from services import indexer

log = logging.getLogger(__name__)

if settings.index_channels:

    @Client.on_message(
        filters.chat(list(settings.index_channels))
        & (filters.document | filters.video | filters.audio),
        group=0,
    )
    async def index_new_media(client: Client, message):
        status = await indexer.save_message(message)
        log.debug("channel index -> %s (%s)", status, message.id)

    __all__ = ["index_new_media"]

else:  # pragma: no cover - nothing to register
    __all__ = []
