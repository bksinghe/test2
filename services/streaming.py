"""Streaming helpers: one bin channel message per file and signed links."""

from __future__ import annotations

import hashlib
import hmac
import logging

from pyrogram import Client
from pyrogram.types import Message

from config import settings
from db import meta

log = logging.getLogger(__name__)


async def ensure_message(client: Client, file_id: str) -> Message | None:
    """Return the BIN_CHANNEL message that holds ``file_id``.

    The old code re-uploaded the file to the bin channel on every click, which
    duplicated messages forever. The message id is cached in Mongo now.
    """
    cached = await meta.cached_stream_message(file_id)
    if cached:
        try:
            message = await client.get_messages(settings.bin_channel, cached)
            if message and not getattr(message, "empty", True):
                return message
        except Exception as error:  # noqa: BLE001 - message may be gone
            log.debug("stream cache stale for %s: %s", file_id, error)
        await meta.forget_stream_message(file_id)

    try:
        message = await client.send_cached_media(chat_id=settings.bin_channel, file_id=file_id)
    except Exception as error:  # noqa: BLE001
        log.warning("could not cache file in bin channel: %s", error)
        return None

    if not message:
        return None
    await meta.cache_stream_message(file_id, message.id)
    return message


def sign(message_id: int) -> str:
    """Short HMAC used to protect direct download links (optional)."""
    if not settings.stream_secret:
        return ""
    digest = hmac.new(
        settings.stream_secret.encode(), str(int(message_id)).encode(), hashlib.sha256
    )
    return digest.hexdigest()[:16]


def verify_token(message_id: int, token: str | None) -> bool:
    if not settings.stream_secret:
        return True
    return hmac.compare_digest(sign(int(message_id)), token or "")


def urls(message_id: int) -> tuple[str, str]:
    token = sign(message_id)
    suffix = f"?token={token}" if token else ""
    return f"{settings.url}watch/{message_id}{suffix}", f"{settings.url}download/{message_id}{suffix}"


__all__ = ["ensure_message", "sign", "urls", "verify_token"]
