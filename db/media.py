"""Indexed media documents.

A plain motor collection is used instead of the previous ``umongo`` model:
the dependency is gone, bookkeeping is explicit and every function is easy to
unit test with a fake collection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from pymongo.errors import DuplicateKeyError

from db import mongo

CLEAN_NAME = re.compile(r"@\w+|(_|-|\.|\+)")
SORT_NEWEST = [("$natural", -1)]


@dataclass(slots=True)
class MediaFile:
    file_id: str
    file_name: str
    file_size: int
    caption: str = ""

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> MediaFile:
        return cls(
            file_id=str(doc.get("_id", "")),
            file_name=doc.get("file_name", ""),
            file_size=int(doc.get("file_size") or 0),
            caption=doc.get("caption") or "",
        )

    def to_doc(self) -> dict[str, Any]:
        return {
            "_id": self.file_id,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "caption": self.caption,
        }


def clean_name(value: str | None) -> str:
    """Normalise a file name/caption for search (``None`` -> empty string)."""
    return CLEAN_NAME.sub(" ", str(value or "")).strip()


async def save(file_id: str, file_name: str | None, file_size: int, caption: str | None) -> str:
    """Store a file. Returns ``saved``, ``duplicate`` or ``invalid``."""
    if not file_id:
        return "invalid"
    doc = MediaFile(
        file_id=file_id,
        file_name=clean_name(file_name) or "unknown",
        file_size=int(file_size or 0),
        caption=clean_name(caption),
    )
    try:
        await mongo.media.insert_one(doc.to_doc())
    except DuplicateKeyError:
        return "duplicate"
    except Exception:  # noqa: BLE001 - never let indexing die on one file
        return "invalid"
    return "saved"


async def get(file_id: str) -> MediaFile | None:
    doc = await mongo.media.find_one({"_id": file_id})
    return MediaFile.from_doc(doc) if doc else None


async def count(filt: dict[str, Any] | None = None) -> int:
    return await mongo.media.count_documents(filt or {})


async def find(filt: dict[str, Any], skip: int = 0, limit: int = 10) -> list[MediaFile]:
    cursor = mongo.media.find(filt).sort(SORT_NEWEST).skip(max(skip, 0)).limit(max(limit, 1))
    return [MediaFile.from_doc(doc) async for doc in cursor]


async def delete(filt: dict[str, Any]) -> int:
    result = await mongo.media.delete_many(filt)
    return int(result.deleted_count)


async def drop() -> int:
    total = await count()
    await mongo.media.drop()
    await mongo.ensure_indexes()
    return total


__all__ = ["MediaFile", "clean_name", "count", "delete", "drop", "find", "get", "save"]
