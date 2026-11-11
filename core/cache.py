"""Tiny TTL + LRU cache used for all the bot's in memory state.

The previous version kept plain dicts (``temp.FILES``, ``temp.SETTINGS`` …)
which grew without limit. This keeps memory bounded and expires stale
entries automatically.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Iterator
from typing import Any


class TTLCache:
    """Ordered dict with a time to live and a maximum size."""

    __slots__ = ("_ttl", "_maxsize", "_data", "_now")

    def __init__(self, ttl: float, maxsize: int = 1024) -> None:
        self._ttl = float(ttl)
        self._maxsize = max(1, int(maxsize))
        self._data: OrderedDict[Any, tuple[float, Any]] = OrderedDict()
        self._now = time.monotonic

    # -- internals -----------------------------------------------------
    def _expire(self) -> None:
        now = self._now()
        while self._data:
            key, (stamp, _) = next(iter(self._data.items()))
            if now - stamp <= self._ttl:
                break
            self._data.popitem(last=False)

    def _trim(self) -> None:
        while len(self._data) > self._maxsize:
            self._data.popitem(last=False)

    # -- public api ----------------------------------------------------
    def get(self, key: Any, default: Any = None) -> Any:
        self._expire()
        item = self._data.get(key)
        if item is None:
            return default
        self._data.move_to_end(key)
        return item[1]

    def set(self, key: Any, value: Any) -> Any:
        self._data[key] = (self._now(), value)
        self._data.move_to_end(key)
        self._trim()
        return value

    def pop(self, key: Any, default: Any = None) -> Any:
        item = self._data.pop(key, None)
        return default if item is None else item[1]

    def clear(self) -> None:
        self._data.clear()

    def __getitem__(self, key: Any) -> Any:
        sentinel = object()
        value = self.get(key, sentinel)
        if value is sentinel:
            raise KeyError(key)
        return value

    def __setitem__(self, key: Any, value: Any) -> None:
        self.set(key, value)

    def __contains__(self, key: Any) -> bool:
        self._expire()
        return key in self._data

    def __len__(self) -> int:
        self._expire()
        return len(self._data)

    def __iter__(self) -> Iterator[Any]:
        self._expire()
        return iter(list(self._data))


__all__ = ["TTLCache"]
