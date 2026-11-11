"""The Telegram failure modes from the production logs.

Each test reproduces a real traceback from the old bot:

* ``MessageIdInvalid`` on ``query.message.edit_text`` (buttons kept in old chats)
* ``MessageNotModified`` when a page is rendered twice
* ``QueryIdInvalid`` when a button is pressed twice / the bot answers late
* ``UserIsBlocked`` on ``/start`` photo send
* ``MessageIdInvalid`` on ``message.react``
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageIdInvalid, MessageNotModified, QueryIdInvalid, UserIsBlocked

from core.telegram import safe_answer, safe_edit, safe_edit_markup, safe_react, safe_send


class FakeClient:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.deleted: list[int] = []
        self.error: Exception | None = None

    async def send_message(self, **kwargs):
        if self.error:
            raise self.error
        self.sent.append(kwargs)
        return SimpleNamespace(id=999, chat=SimpleNamespace(id=kwargs.get("chat_id")))

    async def delete_messages(self, chat_id, message_ids):
        self.deleted.extend(message_ids if isinstance(message_ids, list) else [message_ids])


class FakeMessage:
    def __init__(self, *, message_id=5, chat_id=42, photo=None, video=None, error=None, client=None):
        self.id = message_id
        self.chat = SimpleNamespace(id=chat_id)
        self.photo = photo
        self.video = video
        self.error = error
        self._client = client or FakeClient()
        self.edits: list[dict] = []
        self.captions: list[dict] = []
        self.markups: list[dict] = []
        self.reactions: list[str] = []

    def _maybe_raise(self):
        if self.error:
            raise self.error

    async def edit_text(self, text, **kwargs):
        self._maybe_raise()
        self.edits.append({"text": text, **kwargs})

    async def edit_caption(self, caption, **kwargs):
        self._maybe_raise()
        self.captions.append({"caption": caption, **kwargs})

    async def edit_reply_markup(self, reply_markup=None):
        self._maybe_raise()
        self.markups.append({"markup": reply_markup})

    async def react(self, emoji, big=False):
        self._maybe_raise()
        self.reactions.append(emoji)


class FakeQuery:
    def __init__(self, error=None):
        self.error = error
        self.answers: list[dict] = []

    async def answer(self, text=None, show_alert=False, url=None, cache_time=0):
        if self.error:
            raise self.error
        self.answers.append({"text": text, "alert": show_alert, "url": url})


# --------------------------------------------------------------------- edits
def test_edit_ignores_unchanged_content():
    message = FakeMessage(error=MessageNotModified())
    assert asyncio.run(safe_edit(message, "same")) is True
    assert message.edits == []


def test_expired_message_is_replaced_with_a_new_one():
    message = FakeMessage(error=MessageIdInvalid(), chat_id=42)
    assert asyncio.run(safe_edit(message, "page 2", markup="kb")) is True
    client = message._client
    assert client.deleted == [5]
    assert client.sent == [
        {
            "chat_id": 42,
            "text": "page 2",
            "reply_markup": "kb",
            "parse_mode": ParseMode.HTML,
            "disable_web_page_preview": True,
            "reply_to_message_id": None,
            "protect_content": False,
        }
    ]


def test_photo_message_edits_the_caption():
    message = FakeMessage(photo=object())
    assert asyncio.run(safe_edit(message, "caption")) is True
    assert message.captions and message.edits == []


def test_long_text_is_clipped():
    message = FakeMessage()
    asyncio.run(safe_edit(message, "x" * 5000))
    assert len(message.edits[0]["text"]) == 4096


def test_edit_markup_ignores_not_modified():
    message = FakeMessage(error=MessageNotModified())
    assert asyncio.run(safe_edit_markup(message, "kb")) is True


# ------------------------------------------------------------------- answers
def test_stale_callback_query_does_not_raise():
    query = FakeQuery(error=QueryIdInvalid())
    assert asyncio.run(safe_answer(query, "Closed!")) is False


def test_answer_alert_is_forwarded():
    query = FakeQuery()
    assert asyncio.run(safe_answer(query, "nope", show_alert=True)) is True
    assert query.answers == [{"text": "nope", "alert": True, "url": None}]


# --------------------------------------------------------------------- sends
def test_send_to_blocking_user_returns_none():
    client = FakeClient()
    client.error = UserIsBlocked()
    assert asyncio.run(safe_send(1, "hi", client=client)) is None


def test_send_without_client_is_a_no_op():
    assert asyncio.run(safe_send(1, "hi")) is None


# ------------------------------------------------------------------ reactions
def test_old_message_reaction_is_swallowed():
    message = FakeMessage(error=MessageIdInvalid())
    asyncio.run(safe_react(message, ["🔥", "⚡️"]))
    assert message.reactions == []


def test_first_working_reaction_wins():
    message = FakeMessage()
    asyncio.run(safe_react(message, ["🔥", "⚡️"]))
    assert message.reactions == ["🔥"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__]))
