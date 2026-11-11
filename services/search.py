"""Query building and paginated search against the media index.

Query building is a pure function so it can be unit tested without MongoDB.
Language/quality filtering is pushed into the database query instead of
pulling every document into Python like the old implementation did.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from config import settings
from db import media


def _pattern(query: str) -> str:
    query = (query or "").strip()
    if not query:
        return "."
    if " " not in query:
        token = re.escape(query)
        return rf"(\b|[\.\+\-_]){token}(\b|[\.\+\-_])"
    tokens = [re.escape(token) for token in query.split()]
    return r".*[\s\.\+\-_]".join(tokens)


def compile_query(query: str) -> re.Pattern[str]:
    """Compile the user query into a case insensitive regex."""
    return re.compile(_pattern(query), re.IGNORECASE)


def _text_filter(pattern: re.Pattern[str], caption_filter: bool) -> dict[str, Any]:
    if caption_filter:
        return {"$or": [{"file_name": pattern}, {"caption": pattern}]}
    return {"file_name": pattern}


def build_filter(
    query: str,
    *,
    lang: str = "",
    quality: str = "",
    caption_filter: bool | None = None,
) -> dict[str, Any]:
    use_caption = settings.caption_filter if caption_filter is None else caption_filter
    clauses = [_text_filter(compile_query(query), use_caption)]
    for extra in (lang, quality):
        if not extra:
            continue
        literal = re.compile(re.escape(extra), re.IGNORECASE)
        clauses.append(_text_filter(literal, use_caption))
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


@dataclass(slots=True)
class SearchResult:
    files: list[media.MediaFile]
    total: int
    offset: int
    limit: int
    next_offset: int | str

    @property
    def page(self) -> int:
        return self.offset // self.limit + 1

    @property
    def pages(self) -> int:
        return max(1, math.ceil(self.total / self.limit))


async def search(
    query: str,
    *,
    offset: int = 0,
    limit: int | None = None,
    lang: str = "",
    quality: str = "",
) -> SearchResult:
    limit = max(1, limit or settings.max_btn)
    offset = max(0, int(offset or 0))
    filt = build_filter(query, lang=lang, quality=quality)
    files = await media.find(filt, skip=offset, limit=limit)
    total = await media.count(filt)
    next_offset: int | str = offset + limit if offset + limit < total else ""
    return SearchResult(files=files, total=total, offset=offset, limit=limit, next_offset=next_offset)


async def count(query: str) -> int:
    return await media.count(build_filter(query))


async def find_all(query: str, limit: int | None = None) -> list[media.MediaFile]:
    return await media.find(
        build_filter(query), skip=0, limit=limit or settings.send_all_limit
    )


async def delete_matching(query: str) -> tuple[int, dict[str, Any]]:
    filt = build_filter(query, caption_filter=False)
    return await media.count(filt), filt


__all__ = [
    "SearchResult",
    "build_filter",
    "compile_query",
    "count",
    "delete_matching",
    "find_all",
    "search",
]
