"""Reusable Pyrogram filters."""

from __future__ import annotations

from pyrogram import filters

from core import state


def _banned(_: object, __: object, message) -> bool:
    user = getattr(message, "from_user", None)
    return bool(user and user.id in state.banned_users)


def _not_banned(_: object, __: object, message) -> bool:
    return not _banned(_, __, message)


def _disabled(_: object, __: object, message) -> bool:
    chat = getattr(message, "chat", None)
    return bool(chat and chat.id in state.banned_chats)


def _enabled(_: object, __: object, message) -> bool:
    return not _disabled(_, __, message)


def _is_command(_: object, __: object, message) -> bool:
    text = getattr(message, "text", None)
    return bool(text and text.startswith("/"))


def _not_command(_: object, __: object, message) -> bool:
    return not _is_command(_, __, message)


banned_user = filters.create(_banned, "BannedUser")
not_banned = filters.create(_not_banned, "NotBanned")
disabled_chat = filters.create(_disabled, "DisabledChat")
chat_enabled = filters.create(_enabled, "ChatEnabled")
is_command = filters.create(_is_command, "IsCommand")
not_command = filters.create(_not_command, "NotCommand")


__all__ = [
    "banned_user",
    "chat_enabled",
    "disabled_chat",
    "is_command",
    "not_banned",
    "not_command",
]
