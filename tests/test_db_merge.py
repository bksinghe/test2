"""Duplicate document merging and the legacy schema migration.

The production database had two ``Users`` documents with ``id: 5025490460``
(the old bot did ``find_one`` + ``insert`` without a unique index), which made
``create_index(unique=True)`` abort the whole startup. These tests cover the
merge logic and the migration expressions that fix such a database.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from db import migrate, mongo
from db.mongo import merge_chat_docs, merge_user_docs


# ----------------------------------------------------------------- merging
def test_merge_keeps_ban_premium_and_trial():
    banned = {
        "_id": "a",
        "id": 7,
        "name": "old",
        "banned": {"is_banned": True, "reason": "spam"},
        "verify": {"verified": False},
    }
    premium = {
        "_id": "b",
        "id": 7,
        "premium_until": datetime(2030, 1, 1, tzinfo=UTC),
        "trial_used": True,
        "created_at": datetime(2024, 1, 1, tzinfo=UTC),
    }
    merged = merge_user_docs([banned, premium])
    assert merged["id"] == 7
    assert merged["banned"] == {"is_banned": True, "reason": "spam"}
    assert merged["premium_until"] == datetime(2030, 1, 1, tzinfo=UTC)
    assert merged["trial_used"] is True
    assert merged["created_at"] == datetime(2024, 1, 1, tzinfo=UTC)


def test_merge_prefers_the_verified_row_and_earliest_creation():
    rows = [
        {"_id": 1, "id": 9, "verify": {"verified": True, "verified_at": "2024-05-01"}},
        {"_id": 2, "id": 9, "verify": {"verified": True, "verified_at": "2023-05-01"},
         "created_at": datetime(2023, 1, 1, tzinfo=UTC)},
    ]
    merged = merge_user_docs(rows)
    assert merged["verify"]["verified"] is True
    assert merged["created_at"] == datetime(2023, 1, 1, tzinfo=UTC)


def test_merge_chats_unions_settings_and_keeps_disabled():
    rows = [
        {"_id": 1, "id": -100, "settings": {"imdb": False, "template": "x"}},
        {"_id": 2, "id": -100, "disabled": {"is_disabled": True, "reason": "dmca"},
         "settings": {"imdb": True, "auto_filter": True}},
    ]
    merged = merge_chat_docs(rows)
    assert merged["disabled"]["is_disabled"] is True
    assert merged["settings"]["imdb"] is True  # true wins, false is "empty"
    assert merged["settings"]["template"] == "x"
    assert merged["settings"]["auto_filter"] is True


# ------------------------------------------------------------------ dedupe
class Cursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._docs:
            raise StopAsyncIteration
        return self._docs.pop(0)


class FakeCollection:
    """Just enough motor API for :func:`db.mongo.dedupe`."""

    def __init__(self, name, docs):
        self.name = name
        self.docs = [dict(doc) for doc in docs]

    def aggregate(self, pipeline, allowDiskUse=False):
        counts: dict = {}
        for doc in self.docs:
            counts[doc.get("id")] = counts.get(doc.get("id"), 0) + 1
        return Cursor([{"_id": key, "count": value} for key, value in counts.items() if value > 1])

    def find(self, query):
        return Cursor([doc for doc in self.docs if doc.get("id") == query.get("id")])

    async def replace_one(self, query, document, upsert=False):
        for index, doc in enumerate(self.docs):
            if doc["_id"] == query["_id"]:
                self.docs[index] = dict(document)
                return

    async def delete_many(self, query):
        ids = set(query["_id"]["$in"])
        self.docs = [doc for doc in self.docs if doc["_id"] not in ids]


def test_dedupe_merges_duplicate_users():
    collection = FakeCollection(
        "Users",
        [
            {"_id": "a", "id": 5025490460, "banned": {"is_banned": True, "reason": "spam"}},
            {"_id": "b", "id": 5025490460, "banned": {"is_banned": False, "reason": ""}},
            {"_id": "c", "id": 42, "banned": {"is_banned": False, "reason": ""}},
        ],
    )
    removed = asyncio.run(mongo.dedupe(collection))
    assert removed == 1
    survivors = sorted(collection.docs, key=lambda doc: doc["id"])
    assert [doc["id"] for doc in survivors] == [42, 5025490460]
    kept = next(doc for doc in survivors if doc["id"] == 5025490460)
    assert kept["banned"]["is_banned"] is True


# --------------------------------------------------------------- migration
def test_user_pipeline_converts_and_drops_legacy_fields():
    set_stage, unset_stage = migrate.USER_PIPELINE
    assert set(set_stage["$set"]) >= {"banned", "verify", "premium_until", "trial_used", "id"}
    assert sorted(unset_stage["$unset"]) == ["ban_status", "verify_status"]


def test_timestamp_expression_accepts_epoch_and_dates():
    expression = migrate._timestamp("$verify_status.verified_time")
    branches = expression["$switch"]["branches"]
    assert branches[0]["case"]["$eq"] == [{"$type": "$verify_status.verified_time"}, "date"]
    assert branches[1]["then"]["$toDate"]["$multiply"] == [
        "$verify_status.verified_time",
        1000,
    ]


def test_every_chat_setting_key_is_migrated():
    from services.settings import DEFAULTS_KEYS

    assert set(migrate.SETTING_KEYS) == set(DEFAULTS_KEYS)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (1700000000, datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)),
        (datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 1, 1, tzinfo=UTC)),
        (datetime(2024, 1, 1), datetime(2024, 1, 1, tzinfo=UTC)),
        (None, None),
        (0, None),
        ("not-a-date", None),
    ],
)
def test_as_datetime(raw, expected):
    assert migrate._as_datetime(raw) == expected


def test_as_int():
    assert migrate._as_int("5025490460") == 5025490460
    assert migrate._as_int(None) is None
    assert migrate._as_int("abc") is None
