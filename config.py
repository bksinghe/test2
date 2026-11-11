"""Environment driven configuration.

Importing this module never exits the process: problems are collected and
reported by :meth:`Settings.validate`, which the bot calls once on startup.
That keeps the package importable for tooling and tests.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

TRUTHY = {"1", "true", "yes", "y", "on", "enable", "enabled"}
FALSY = {"0", "false", "no", "n", "off", "disable", "disabled"}

_IPV4 = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")

_warnings: list[str] = []


def warnings() -> list[str]:
    """Non fatal configuration problems collected while parsing the env."""
    return list(_warnings)


def _raw(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return default if value is None else value.strip()


def _bool(name: str, default: bool) -> bool:
    raw = _raw(name)
    if not raw:
        return default
    low = raw.lower()
    if low in TRUTHY:
        return True
    if low in FALSY:
        return False
    _warnings.append(f"{name}={raw!r} is not a boolean - using {default!r}")
    return default


def _int(name: str, default: int) -> int:
    raw = _raw(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        _warnings.append(f"{name}={raw!r} is not an integer - using {default!r}")
        return default


def _tokens(name: str, default: str = "") -> tuple[str, ...]:
    return tuple(_raw(name, default).split())


def _id_list(name: str) -> tuple[int, ...]:
    ids: list[int] = []
    for token in _tokens(name):
        try:
            ids.append(int(token))
        except ValueError:
            _warnings.append(f"{name}: {token!r} is not a chat id - ignored")
    return tuple(ids)


def _index_channels() -> tuple[int | str, ...]:
    """Channels may be numeric ids or public usernames."""
    channels: list[int | str] = []
    for token in _tokens("INDEX_CHANNELS"):
        try:
            channels.append(int(token))
        except ValueError:
            channels.append(token)
    return tuple(channels)


def _base_url(raw: str) -> str:
    """Normalise the public base URL used for streaming links."""
    if not raw:
        return ""
    if raw.startswith(("http://", "https://")):
        return raw if raw.endswith("/") else f"{raw}/"
    if _IPV4.match(raw):
        return f"http://{raw}/"
    _warnings.append(f"URL={raw!r} is not a valid url - streaming links disabled")
    return ""


@dataclass(frozen=True, slots=True)
class Settings:
    # telegram
    api_id: int = 0
    api_hash: str = ""
    bot_token: str = ""
    session_name: str = "auto_filter_bot"
    workers: int = 8

    # admins / channels
    admins: tuple[int, ...] = ()
    log_channel: int = 0
    support_group: int = 0
    index_channels: tuple[int | str, ...] = ()
    bin_channel: int = 0

    # database
    database_url: str = ""
    database_name: str = "Cluster0"
    media_collection: str = "Files"
    users_collection: str = "Users"
    chats_collection: str = "Groups"
    meta_collection: str = "BotMeta"
    stream_collection: str = "Streams"

    # links
    url: str = ""
    support_link: str = "https://t.me/Telegram"
    updates_link: str = "https://t.me/Telegram"
    films_link: str = "https://t.me/Telegram"
    tutorial: str = "https://t.me/Telegram"
    verify_tutorial: str = "https://t.me/Telegram"
    owner_username: str = "https://t.me/Telegram"

    # payments
    payment_qr: str = ""
    owner_upi: str = "sampleupi@upi"

    # behaviour knobs
    timezone: str = "Asia/Colombo"
    port: int = 80
    pics: tuple[str, ...] = ()
    reactions: tuple[str, ...] = ("🔥", "👍", "🎉", "⚡️", "🤩")
    max_btn: int = 10
    cache_time: int = 300
    delete_time: int = 3600
    pm_delete_time: int = 3600
    verify_expire: int = 86400
    storage_limit: int = 512 * 1024 * 1024
    send_all_limit: int = 50
    languages: tuple[str, ...] = ("Hindi", "English", "Tamil", "Telugu")
    quality: tuple[str, ...] = ("360p", "480p", "720p", "1080p")

    # text defaults (per group overrides live in the database)
    imdb_template: str = ""
    file_caption: str = ""
    welcome_text: str = ""

    # shortlink / verification
    shortlink_url: str = ""
    shortlink_api: str = ""

    # feature flags
    pm_search: bool = True
    verify: bool = True
    auto_delete: bool = False
    welcome: bool = True
    protect_content: bool = False
    long_imdb: bool = False
    link_mode: bool = True
    auto_filter: bool = True
    imdb: bool = False
    spell_check: bool = True
    shortlink: bool = False
    is_stream: bool = True
    caption_filter: bool = True

    # streaming security (optional)
    stream_secret: str = ""

    @classmethod
    def from_env(cls) -> Settings:
        from ui.defaults import DEFAULT_FILE_CAPTION, DEFAULT_IMDB_TEMPLATE, DEFAULT_WELCOME

        return cls(
            api_id=_int("API_ID", 0),
            api_hash=_raw("API_HASH"),
            bot_token=_raw("BOT_TOKEN"),
            session_name=_raw("SESSION_NAME", "auto_filter_bot"),
            workers=_int("WORKERS", 8),
            admins=_id_list("ADMINS"),
            log_channel=_int("LOG_CHANNEL", 0),
            support_group=_int("SUPPORT_GROUP", 0),
            index_channels=_index_channels(),
            bin_channel=_int("BIN_CHANNEL", 0),
            database_url=_raw("DATABASE_URL"),
            database_name=_raw("DATABASE_NAME", "Cluster0"),
            media_collection=_raw("COLLECTION_NAME", "Files"),
            users_collection=_raw("USERS_COLLECTION", "Users"),
            chats_collection=_raw("CHATS_COLLECTION", "Groups"),
            meta_collection=_raw("META_COLLECTION", "BotMeta"),
            stream_collection=_raw("STREAM_COLLECTION", "Streams"),
            url=_base_url(_raw("URL")),
            support_link=_raw("SUPPORT_LINK", "https://t.me/Telegram"),
            updates_link=_raw("UPDATES_LINK", "https://t.me/Telegram"),
            films_link=_raw("FILMS_LINK", "https://t.me/Telegram"),
            tutorial=_raw("TUTORIAL", "https://t.me/Telegram"),
            verify_tutorial=_raw("VERIFY_TUTORIAL", "https://t.me/Telegram"),
            owner_username=_raw("OWNER_USERNAME", "https://t.me/Telegram"),
            payment_qr=_raw("PAYMENT_QR"),
            owner_upi=_raw("OWNER_UPI_ID", "sampleupi@upi"),
            timezone=_raw("TIMEZONE", "Asia/Colombo"),
            port=_int("PORT", 80),
            pics=_tokens(
                "PICS",
                "https://telegra.ph/file/58fef5cb458d5b29b0186.jpg "
                "https://telegra.ph/file/f0aa4f433132769f8970c.jpg",
            ),
            reactions=_tokens("REACTIONS", "🔥 👍 🎉 ⚡️ 🤩 😍 😎 🏆"),
            max_btn=max(1, _int("MAX_BTN", 10)),
            cache_time=_int("CACHE_TIME", 300),
            delete_time=_int("DELETE_TIME", 3600),
            pm_delete_time=_int("PM_FILE_DELETE_TIME", 3600),
            verify_expire=_int("VERIFY_EXPIRE", 86400),
            storage_limit=_int("STORAGE_LIMIT", 512 * 1024 * 1024),
            send_all_limit=_int("SEND_ALL_LIMIT", 50),
            languages=_tokens("LANGUAGES", "Hindi English Tamil Telugu"),
            quality=_tokens("QUALITY", "360p 480p 720p 1080p"),
            imdb_template=_raw("IMDB_TEMPLATE", DEFAULT_IMDB_TEMPLATE),
            file_caption=_raw("FILE_CAPTION", DEFAULT_FILE_CAPTION),
            welcome_text=_raw("WELCOME_TEXT", DEFAULT_WELCOME),
            shortlink_url=_raw("SHORTLINK_URL"),
            shortlink_api=_raw("SHORTLINK_API"),
            pm_search=_bool("IS_PM_SEARCH", True),
            verify=_bool("IS_VERIFY", True),
            auto_delete=_bool("AUTO_DELETE", False),
            welcome=_bool("WELCOME", True),
            protect_content=_bool("PROTECT_CONTENT", False),
            long_imdb=_bool("LONG_IMDB_DESCRIPTION", False),
            link_mode=_bool("LINK_MODE", True),
            auto_filter=_bool("AUTO_FILTER", True),
            imdb=_bool("IMDB", False),
            spell_check=_bool("SPELL_CHECK", True),
            shortlink=_bool("SHORTLINK", False),
            is_stream=_bool("IS_STREAM", True),
            caption_filter=_bool("USE_CAPTION_FILTER", True),
            stream_secret=_raw("STREAM_SECRET"),
        )

    # -- helpers ---------------------------------------------------------
    def is_admin(self, user_id: int | None) -> bool:
        return user_id is not None and user_id in self.admins

    def media_enabled(self) -> bool:
        return bool(self.url and self.bin_channel)

    def validate(self) -> list[str]:
        """Return a list of fatal problems (empty list means all good)."""
        problems: list[str] = []
        required = {
            "API_ID": self.api_id,
            "API_HASH": self.api_hash,
            "BOT_TOKEN": self.bot_token,
            "ADMINS": self.admins,
            "LOG_CHANNEL": self.log_channel,
            "DATABASE_URL": self.database_url,
        }
        for name, value in required.items():
            if not value:
                problems.append(f"{name} is required")

        if self.is_stream and not self.media_enabled():
            problems.append("URL and BIN_CHANNEL are required when IS_STREAM is enabled")

        if self.shortlink and not (self.shortlink_url and self.shortlink_api):
            _warnings.append("SHORTLINK is enabled without a global shortlink url/api")
        return problems

    def masked(self) -> dict[str, object]:
        """Safe snapshot for startup logging."""
        return {
            "admins": len(self.admins),
            "index_channels": len(self.index_channels),
            "database": self.database_name,
            "stream": self.media_enabled(),
            "verify": self.verify,
            "shortlink": self.shortlink,
        }


settings = Settings.from_env()

__all__ = ["Settings", "settings", "warnings", "field"]
