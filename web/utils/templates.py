"""Minimal HTML rendering for the watch page."""

from __future__ import annotations

import html
import mimetypes
from pathlib import Path

from config import settings
from core import state
from services import streaming
from web.utils.custom_dl import TGCustomYield

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
WATCH_TEMPLATE = TEMPLATE_DIR / "watch.html"

_template_cache: str | None = None

ERROR_PAGE = "<h1 style='font-family:sans-serif'>This file is not available.</h1>"
NOT_STREAMABLE = "<h1 style='font-family:sans-serif'>This file cannot be streamed.</h1>"


def _template() -> str:
    global _template_cache
    if _template_cache is None:
        _template_cache = WATCH_TEMPLATE.read_text(encoding="utf-8")
    return _template_cache


def _media_tag(kind: str, src: str) -> str:
    return (
        f'<{kind} src="{html.escape(src, quote=True)}" class="player" '
        "controls playsinline preload=\"metadata\"></" + kind + ">"
    )


async def render_watch(message_id: int) -> str:
    message = await state.bot.get_messages(settings.bin_channel, message_id)
    if message is None or getattr(message, "empty", True) or message.media is None:
        return ERROR_PAGE

    properties = await TGCustomYield.generate_file_properties(message)
    mime_type = properties.mime_type or mimetypes.guess_type(properties.file_name or "")[0] or ""
    kind = mime_type.split("/")[0]

    if kind not in ("video", "audio"):
        return NOT_STREAMABLE

    _, download_url = streaming.urls(message_id)
    title = f"Watch - {properties.file_name}" if properties.file_name else "Watch"
    return (
        _template()
        .replace("{{title}}", html.escape(title))
        .replace("{{file_name}}", html.escape(properties.file_name or "media"))
        .replace("{{media_tag}}", _media_tag(kind, download_url))
    )


__all__ = ["render_watch"]
