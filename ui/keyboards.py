"""Inline keyboard factory.

Callback data grammar (kept short, Telegram caps it at 64 bytes):

    close
    menu#<start|about|help|user_cmd|admin_cmd|stats|plans>
    plans#buy
    trial
    settings#<key>#<chat_id>
    nav#<key>#<req>#<offset>
    navf#<type>#<value>#<key>#<req>#<offset>
    filtermenu#<type>#<key>#<req>#<offset>
    filter#<type>#<value>#<key>#<req>#<offset>
    sendall#<key>#<req>
    open#<chat_id>#<file_id>
    regain#<file|all>#<chat_id>#<token>
    stream#<file_id>
    checksub#<payload>
    delconfirm#<token>
    deleteall
    mgmt#<action>
    broadcast_cancel#<users|groups>
    index#<yes|no>
"""

from __future__ import annotations

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import settings

CLOSE = "close"


def button(text: str, data: str | None = None, url: str | None = None) -> InlineKeyboardButton:
    if url:
        return InlineKeyboardButton(text, url=url)
    return InlineKeyboardButton(text, callback_data=data)


def rows(*row: InlineKeyboardButton) -> list[list[InlineKeyboardButton]]:
    return [list(r) for r in row]


def close_row() -> list[InlineKeyboardButton]:
    return [button("🙅 Close", CLOSE)]


def close_keyboard(extra: list[list[InlineKeyboardButton]] | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup((extra or []) + [close_row()])


# ------------------------------------------------------------------ start
def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [button("➕️ Add me to your group ➕", url=f"https://t.me/{settings_bot_username()}?startgroup=start")],
            [
                button("🙋 Help", "menu#help"),
                button("🔍 Search", url=f"https://t.me/{settings_bot_username()}?start=start"),
                button("🦹 About", "menu#about"),
            ],
            [button("💰 Buy subscription", "menu#plans")],
        ]
    )


def settings_bot_username() -> str:
    """Filled in at runtime by :mod:`core.state` once the bot is online."""
    from core import state

    return state.username or "bot"


def group_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [button("⚡️ Updates", url=settings.updates_link), button("💡 Support", url=settings.support_link)],
            close_row(),
        ]
    )


# ------------------------------------------------------------------ menus
def about_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [button("♻️ Status", "menu#stats")],
            [button("🏡 Home", "menu#start")],
        ]
    )


def help_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [button("🦉 User commands", "menu#user_cmd"), button("🦹 Admin commands", "menu#admin_cmd")],
            [button("🏡 Home", "menu#start")],
        ]
    )


def back_keyboard(target: str = "menu#help") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[button("🏄 Back", target)]])


def plans_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [button("🧾 Send payment receipt", url=settings.owner_username)],
            [button("⚠️ Close / Delete ⚠️", CLOSE)],
        ]
    )


def trial_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [button("ɢᴇᴛ ꜰʀᴇᴇ ᴛʀɪᴀʟ ꜰᴏʀ 5 ᴍɪɴᴜᴛᴇs ☺️", "trial")],
            [button("ʙᴜʏ sᴜʙsᴄʀɪᴘᴛɪᴏɴ : ʀᴇᴍᴏᴠᴇ ᴀᴅs", "menu#plans")],
            close_row(),
        ]
    )


# --------------------------------------------------------------- settings
_TOGGLES: tuple[tuple[str, str, str], ...] = (
    ("auto_filter", "Auto filter", "✅ Yes|❌ No"),
    ("imdb", "IMDb poster", "✅ Yes|❌ No"),
    ("spell_check", "Spell check", "✅ Yes|❌ No"),
    ("auto_delete", "Auto delete", "✅ Yes|❌ No"),
    ("welcome", "Welcome message", "✅ Yes|❌ No"),
    ("shortlink", "Shortlink", "✅ Yes|❌ No"),
    ("file_secure", "Protect content", "✅ Yes|❌ No"),
    ("links", "Result page", "⛓ Link|🧲 Button"),
    ("is_stream", "Streaming", "✅ On|❌ Off"),
)


def settings_keyboard(chat: dict, chat_id: int) -> InlineKeyboardMarkup:
    rows_: list[list[InlineKeyboardButton]] = []
    for key, label, labels in _TOGGLES:
        enabled = bool(chat.get(key))
        on, off = labels.split("|")
        rows_.append(
            [
                button(label, f"settings#{key}#{chat_id}"),
                button(on if enabled else off, f"settings#{key}#{chat_id}"),
            ]
        )
    rows_.append(close_row())
    return InlineKeyboardMarkup(rows_)


# ---------------------------------------------------------------- results
def filter_menu_keyboard(kind: str, values: tuple[str, ...], key: str, req: int, offset: int) -> InlineKeyboardMarkup:
    rows_: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for value in values:
        pair.append(button(value.title(), f"filter#{kind}#{value}#{key}#{req}#{offset}"))
        if len(pair) == 2:
            rows_.append(pair)
            pair = []
    if pair:
        rows_.append(pair)
    rows_.append([button("🏄 Back to results", f"nav#{key}#{req}#{offset}")])
    return InlineKeyboardMarkup(rows_)


def pagination_row(key: str, req: int, offset: int, next_offset: int | str, page: int, pages: int,
                   filter_type: str = "", filter_value: str = "") -> list[InlineKeyboardButton]:
    prefix = (
        f"navf#{filter_type}#{filter_value}#{key}#{req}"
        if filter_type
        else f"nav#{key}#{req}"
    )
    counter = button(f"🗓 {page}/{max(pages, 1)}", "noop")
    if offset == 0:
        return [counter, button("NEXT ⏩", f"{prefix}#{next_offset}")]
    if not next_offset:
        return [button("⏪ BACK", f"{prefix}#{max(offset - settings.max_btn, 0)}"), counter]
    return [
        button("⏪ BACK", f"{prefix}#{max(offset - settings.max_btn, 0)}"),
        counter,
        button("NEXT ⏩", f"{prefix}#{next_offset}"),
    ]


# ----------------------------------------------------------------- gates
def verify_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [button("🧿 Verify 🧿", url=url)],
            [button("🗳 Tutorial 🗳", url=settings.verify_tutorial)],
        ]
    )


def post_verify_keyboard(payload: str) -> InlineKeyboardMarkup | None:
    if not payload:
        return None
    return InlineKeyboardMarkup(
        [[button("📌 Get file 📌", url=f"https://t.me/{settings_bot_username()}?start={payload}")]]
    )


def fsub_keyboard(join_buttons: list[InlineKeyboardButton], payload: str) -> InlineKeyboardMarkup:
    rows_ = [[btn] for btn in join_buttons]
    rows_.append([button("🔁 Try again 🔁", f"checksub#{payload}")])
    return InlineKeyboardMarkup(rows_)


def file_keyboard(file_id: str, stream: bool) -> InlineKeyboardMarkup:
    rows_: list[list[InlineKeyboardButton]] = []
    if stream:
        rows_.append([button("🚀 Watch and download ⚡", f"stream#{file_id}")])
    rows_.append(close_row())
    return InlineKeyboardMarkup(rows_)


def regain_keyboard(kind: str, chat_id: int, token: str) -> InlineKeyboardMarkup:
    label = "ɢᴇᴛ ғɪʟᴇs ᴀɢᴀɪɴ" if kind == "all" else "ɢᴇᴛ ғɪʟᴇ ᴀɢᴀɪɴ"
    return InlineKeyboardMarkup([[button(label, f"regain#{kind}#{chat_id}#{token}")]])


def watch_keyboard(watch_url: str, download_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [button("⚡ Watch online", url=watch_url), button("🚀 Fast download", url=download_url)],
            close_row(),
        ]
    )


# ----------------------------------------------------------------- admin
def confirm_keyboard(confirm_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[button("✅ Yes", confirm_data)], [button("❌ Close", CLOSE)]]
    )


def manage_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [button("Unmute all", "mgmt#unmute_all"), button("Unban all", "mgmt#unban_all")],
            [button("Kick muted users", "mgmt#kick_muted"), button("Kick deleted accounts", "mgmt#kick_deleted")],
            close_row(),
        ]
    )


def broadcast_cancel_keyboard(target: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[button("CANCEL", f"broadcast_cancel#{target}")]])


def index_confirm_keyboard(chat_id: int | str, last_id: int, skip: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [button("✅ YES", f"index#yes#{chat_id}#{last_id}#{skip}")],
            [button("❌ CLOSE", CLOSE)],
        ]
    )


__all__ = [name for name in dir() if not name.startswith("_")]
