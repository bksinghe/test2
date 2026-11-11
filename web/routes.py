"""HTTP routes: landing page, watch page and range based download."""

from __future__ import annotations

import logging
import mimetypes

from aiohttp import web

from config import settings
from core import state
from services import streaming
from web.utils.custom_dl import TGCustomYield, chunk_size, offset_fix
from web.utils.templates import ERROR_PAGE, render_watch

log = logging.getLogger(__name__)

routes = web.RouteTableDef()

BOUNDARY_MIN = 64 * 1024


@routes.get("/", allow_head=True)
async def index(_: web.Request) -> web.Response:
    body = (
        '<h1 align="center" style="font-family:sans-serif">'
        f'<a href="https://t.me/{settings.support_link.rsplit("/", 1)[-1]}">'
        f"{state.bot_name or 'Auto Filter Bot'}</a></h1>"
    )
    return web.Response(text=body, content_type="text/html")


@routes.get("/watch/{message_id}", allow_head=True)
async def watch(request: web.Request) -> web.Response:
    try:
        message_id = int(request.match_info["message_id"])
        body = await render_watch(message_id)
    except (ValueError, TypeError):
        body = ERROR_PAGE
    except Exception as error:  # noqa: BLE001 - never leak a traceback to a browser
        log.warning("watch page failed: %s", error)
        body = ERROR_PAGE
    return web.Response(text=body, content_type="text/html")


@routes.get("/download/{message_id}", allow_head=True)
async def download(request: web.Request) -> web.StreamResponse:
    try:
        message_id = int(request.match_info["message_id"])
    except (TypeError, ValueError):
        raise web.HTTPBadRequest(text="invalid message id") from None

    if not streaming.verify_token(message_id, request.query.get("token")):
        raise web.HTTPForbidden(text="invalid or missing token")

    message = await state.bot.get_messages(settings.bin_channel, message_id)
    if message is None or getattr(message, "empty", True) or message.media is None:
        raise web.HTTPNotFound(text="file not found")

    try:
        properties = await TGCustomYield.generate_file_properties(message)
    except Exception as error:  # noqa: BLE001
        log.warning("could not read file properties: %s", error)
        raise web.HTTPBadRequest(text="unsupported file") from error

    file_size = int(properties.file_size or 0)
    if file_size <= 0:
        raise web.HTTPNotFound(text="empty file")

    start, end = _range(request, file_size)
    length = end - start + 1

    chunk = max(await chunk_size(length), BOUNDARY_MIN)
    offset = await offset_fix(start, chunk)
    first_cut = start - offset
    last_cut = (end % chunk) + 1
    parts = max(1, -(-length // chunk))

    file_name = _safe_name(properties.file_name or f"file_{message_id}")
    mime_type = (
        properties.mime_type
        or mimetypes.guess_type(file_name)[0]
        or "application/octet-stream"
    )

    stream = web.StreamResponse(
        status=206 if request.headers.get("Range") else 200,
        headers={
            "Content-Type": mime_type,
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'attachment; filename="{file_name}"',
        },
    )
    stream.headers["Content-Length"] = str(file_size if stream.status == 200 else length)
    if stream.status == 206:
        stream.headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"

    await stream.prepare(request)
    feeder = TGCustomYield()
    try:
        async for part in feeder.yield_file(message, offset, first_cut, last_cut, parts, chunk):
            if part:
                await stream.write(part)
    except ConnectionResetError:
        return stream
    except Exception as error:  # noqa: BLE001 - client went away mid-stream
        log.debug("stream aborted for %s: %s", message_id, error)
        return stream
    await stream.write_eof()
    return stream


def _safe_name(name: str) -> str:
    """Strip characters that would break (or inject into) the header."""
    cleaned = name.replace('"', "").replace("\\", "").replace("\r", " ").replace("\n", " ")
    return cleaned.strip() or "file"


def _range(request: web.Request, file_size: int) -> tuple[int, int]:
    header = request.headers.get("Range")
    if header:
        try:
            _, _, spec = header.partition("=")
            raw_start, _, raw_end = spec.partition("-")
            start = int(raw_start) if raw_start else 0
            end = int(raw_end) if raw_end else file_size - 1
        except ValueError:
            return 0, file_size - 1
    else:
        start = request.http_range.start or 0
        end = request.http_range.stop
        end = file_size - 1 if end is None else end

    start = max(0, min(start, file_size - 1))
    end = max(start, min(end, file_size - 1))
    return start, end


__all__ = ["routes"]
