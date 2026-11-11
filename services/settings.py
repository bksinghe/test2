"""Per chat settings with defaults, validation and a short lived cache.

Two bugs from the old implementation are gone:

* the defaults dict was shared, so changing one group's settings mutated the
  defaults for every other group;
* cached settings were never invalidated or evicted.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from config import settings as cfg
from core import state
from db import chats

BOOL_KEYS = {
    "auto_filter",
    "file_secure",
    "imdb",
    "spell_check",
    "auto_delete",
    "welcome",
    "shortlink",
    "links",
    "is_stream",
}
TEXT_KEYS = {"welcome_text", "template", "caption", "url", "api", "tutorial"}

DEFAULTS_KEYS = BOOL_KEYS | TEXT_KEYS | {"fsub"}


def default_settings() -> dict[str, Any]:
    """A fresh copy of the global defaults (never mutate the returned dict in place)."""
    return {
        "auto_filter": cfg.auto_filter,
        "file_secure": cfg.protect_content,
        "imdb": cfg.imdb,
        "spell_check": cfg.spell_check,
        "auto_delete": cfg.auto_delete,
        "welcome": cfg.welcome,
        "welcome_text": cfg.welcome_text,
        "template": cfg.imdb_template,
        "caption": cfg.file_caption,
        "url": cfg.shortlink_url,
        "api": cfg.shortlink_api,
        "shortlink": cfg.shortlink,
        "tutorial": cfg.tutorial,
        "links": cfg.link_mode,
        "fsub": [],
        "is_stream": cfg.is_stream and cfg.media_enabled(),
    }


def normalise(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Merge stored values on top of the defaults and coerce their types."""
    values = default_settings()
    for key, value in (raw or {}).items():
        if key not in DEFAULTS_KEYS:
            continue
        if key in BOOL_KEYS:
            values[key] = bool(value)
        elif key == "fsub":
            values[key] = [int(item) for item in (value or [])]
        else:
            values[key] = "" if value is None else str(value)
    return values


async def get_settings(chat_id: int) -> dict[str, Any]:
    chat_id = int(chat_id)
    cached = state.settings_cache.get(chat_id)
    if cached is not None:
        return deepcopy(cached)

    values = normalise(await chats.stored_settings(chat_id))
    state.settings_cache.set(chat_id, values)
    return deepcopy(values)


def invalidate(chat_id: int) -> None:
    state.settings_cache.pop(int(chat_id))


async def update_setting(chat_id: int, key: str, value: Any) -> dict[str, Any]:
    if key not in DEFAULTS_KEYS:
        raise KeyError(f"unknown setting {key!r}")
    await chats.save_setting(int(chat_id), key, value)
    invalidate(chat_id)
    return await get_settings(chat_id)


async def save_values(chat_id: int, values: dict[str, Any]) -> dict[str, Any]:
    merged = normalise(values)
    await chats.save_settings(int(chat_id), merged)
    invalidate(chat_id)
    return await get_settings(chat_id)


__all__ = [
    "BOOL_KEYS",
    "DEFAULTS_KEYS",
    "TEXT_KEYS",
    "default_settings",
    "get_settings",
    "invalidate",
    "normalise",
    "save_values",
    "update_setting",
]
