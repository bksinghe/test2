"""Small formatting helpers."""

from __future__ import annotations

from collections.abc import Iterable

_UNITS = ("B", "KB", "MB", "GB", "TB", "PB")
_PERIODS = (("d", 86400), ("h", 3600), ("m", 60), ("s", 1))


def human_size(size: float | int | None) -> str:
    value = float(size or 0)
    index = 0
    while value >= 1024 and index < len(_UNITS) - 1:
        value /= 1024
        index += 1
    if index == 0:
        return f"{int(value)} {_UNITS[index]}"
    return f"{value:.2f} {_UNITS[index]}"


def readable_time(seconds: float | int | None) -> str:
    """``3725`` -> ``1h2m5s``. Returns ``0s`` for zero/negative input."""
    remaining = int(seconds or 0)
    if remaining <= 0:
        return "0s"
    parts: list[str] = []
    for name, size in _PERIODS:
        if remaining >= size:
            value, remaining = divmod(remaining, size)
            parts.append(f"{value}{name}")
    return "".join(parts)


def join_iterable(value: Iterable[object] | None, fallback: str = "N/A") -> str:
    if not value:
        return fallback
    items = [str(item) for item in value]
    return items[0] if len(items) == 1 else ", ".join(items)


def shorten(text: str, limit: int = 1024) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


__all__ = ["human_size", "join_iterable", "readable_time", "shorten"]
