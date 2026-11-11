"""Thin, fail soft wrapper around Shortzy."""

from __future__ import annotations

import logging

from shortzy import Shortzy

log = logging.getLogger(__name__)


async def shorten(base_url: str, api_key: str, target: str) -> str | None:
    """Return a shortened url or ``None`` (never raises)."""
    if not (base_url and api_key and target):
        return None
    try:
        return await Shortzy(api_key=api_key, base_site=base_url).convert(target)
    except Exception as error:  # noqa: BLE001 - third party, many failure modes
        log.warning("shortlink failed for %s: %s", base_url, error)
        return None


async def is_valid(base_url: str, api_key: str) -> bool:
    """Used by ``/set_shortlink`` to validate before saving."""
    return bool(await shorten(base_url, api_key, "https://t.me/Telegram"))


__all__ = ["is_valid", "shorten"]
