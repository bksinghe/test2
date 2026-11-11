"""Bot statistics shared by ``/stats`` and the about menu."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from config import settings
from core import state
from core.fmt import human_size, readable_time
from db import chats, media, mongo, users
from ui import texts

log = logging.getLogger(__name__)


@dataclass(slots=True)
class Snapshot:
    files: int
    users: int
    chats: int
    premium: int
    used: int
    free: int
    uptime: str


async def snapshot() -> Snapshot:
    try:
        db_size = int((await mongo.db.command("dbstats"))["dataSize"])
    except Exception as error:  # noqa: BLE001 - stats must never fail a command
        log.debug("dbstats failed: %s", error)
        db_size = 0
    return Snapshot(
        files=await media.count(),
        users=await users.count(),
        chats=await chats.count(),
        premium=await users.premium_count(),
        used=db_size,
        free=max(settings.storage_limit - db_size, 0),
        uptime=readable_time(state.uptime()),
    )


def text(snap: Snapshot) -> str:
    return texts.STATUS.format(
        files=snap.files,
        users=snap.users,
        chats=snap.chats,
        premium=snap.premium,
        used=human_size(snap.used),
        free=human_size(snap.free),
        uptime=snap.uptime,
    )


__all__ = ["Snapshot", "snapshot", "text"]
