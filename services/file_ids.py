"""Stable, DC independent file ids.

Telegram file ids embed the access hash and DC. Re-encoding them into the
compact ``file_type / dc / media_id / access_hash`` form keeps a single row per
file even when the same file is seen through different bots or DCs - this is
the format the original bot stored and it is kept for database compatibility.
"""

from __future__ import annotations

import base64
from struct import pack

from pyrogram.file_id import FileId


def _encode(raw: bytes) -> str:
    result = b""
    zeros = 0
    for byte in raw + bytes([22]) + bytes([4]):
        if byte == 0:
            zeros += 1
            continue
        if zeros:
            result += b"\x00" + bytes([zeros])
            zeros = 0
        result += bytes([byte])
    return base64.urlsafe_b64encode(result).decode().rstrip("=")


def normalize(file_id: str) -> str:
    """Convert any Telegram file id into the compact stored representation."""
    decoded = FileId.decode(file_id)
    return _encode(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash,
        )
    )


__all__ = ["normalize"]
