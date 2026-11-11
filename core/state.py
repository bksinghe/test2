"""Runtime state shared between handlers (replaces the old ``utils.temp``)."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from core.cache import TTLCache

START_TIME: float = time.time()

# filled in by :mod:`core.client` on startup
bot = None
me = None
username: str | None = None
bot_name: str | None = None

banned_users: set[int] = set()
banned_chats: set[int] = set()

# caches
settings_cache: TTLCache = TTLCache(ttl=300, maxsize=5000)
verify_cache: TTLCache = TTLCache(ttl=300, maxsize=10000)
search_cache: TTLCache = TTLCache(ttl=3600 * 6, maxsize=3000)
delete_cache: TTLCache = TTLCache(ttl=600, maxsize=500)
imdb_cache: TTLCache = TTLCache(ttl=3600 * 6, maxsize=2000)

# long running job flags (single instance of each job is enforced by locks)
index_lock = asyncio.Lock()
broadcast_lock = asyncio.Lock()
index_cancel: bool = False
broadcast_cancel: dict[str, bool] = {"users": False, "groups": False}

# strong references to fire-and-forget tasks so they are not garbage collected
background_tasks: set[asyncio.Task] = set()


@dataclass(slots=True)
class SearchSession:
    """Everything needed to re-render a result page later.

    ``key`` is a random token instead of a message id: callback data stays
    short and a session survives edits/deletes of the original message.
    """

    key: str
    query: str
    chat_id: int
    caption: str = ""
    total: int = 0
    message_id: int = 0
    lang: str = ""
    quality: str = ""


def spawn(coro) -> asyncio.Task:
    """Create a background task and keep a reference until it finishes."""
    task = asyncio.create_task(coro)
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    return task


def uptime() -> float:
    return time.time() - START_TIME


__all__ = [
    "START_TIME",
    "SearchSession",
    "background_tasks",
    "banned_chats",
    "banned_users",
    "bot",
    "bot_name",
    "broadcast_cancel",
    "broadcast_lock",
    "delete_cache",
    "imdb_cache",
    "index_cancel",
    "index_lock",
    "me",
    "search_cache",
    "settings_cache",
    "spawn",
    "uptime",
    "username",
    "verify_cache",
    "field",
]
