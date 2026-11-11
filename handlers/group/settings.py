"""Per group configuration commands."""

from __future__ import annotations

import logging

from pyrogram import Client, filters
from pyrogram.enums import ChatType, ParseMode

from handlers.common import group_admin_guard, react
from services import shortlink as shortlink_service
from services.settings import get_settings, update_setting
from ui import keyboards as kb
from ui import texts

log = logging.getLogger(__name__)


def _argument(message) -> str | None:
    parts = message.text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else None


@Client.on_message(filters.command("settings") & filters.group, group=0)
async def settings_cmd(client: Client, message):
    await react(message)
    if not await group_admin_guard(client, message):
        return
    chat_settings = await get_settings(message.chat.id)
    await message.reply_text(
        texts.SETTINGS_TITLE.format(title=message.chat.title),
        reply_markup=kb.settings_keyboard(chat_settings, message.chat.id),
        parse_mode=ParseMode.HTML,
    )


@Client.on_message(filters.command("set_template") & filters.group, group=0)
async def set_template(client: Client, message):
    if not await group_admin_guard(client, message):
        return
    value = _argument(message)
    if not value:
        await message.reply_text(texts.COMMAND_INCOMPLETE.format(usage="/set_template &lt;text&gt;"))
        return
    await update_setting(message.chat.id, "template", value)
    await message.reply_text(texts.SET_TEMPLATE_OK.format(title=message.chat.title))


@Client.on_message(filters.command("set_caption") & filters.group, group=0)
async def set_caption(client: Client, message):
    if not await group_admin_guard(client, message):
        return
    value = _argument(message)
    if not value:
        await message.reply_text(texts.COMMAND_INCOMPLETE.format(usage="/set_caption &lt;text&gt;"))
        return
    await update_setting(message.chat.id, "caption", value)
    await message.reply_text(texts.SET_CAPTION_OK.format(title=message.chat.title))


@Client.on_message(filters.command("set_welcome") & filters.group, group=0)
async def set_welcome(client: Client, message):
    await react(message)
    if not await group_admin_guard(client, message):
        return
    value = _argument(message)
    if not value:
        await message.reply_text(
            texts.COMMAND_INCOMPLETE.format(usage="/set_welcome Hello {mention}")
        )
        return
    await update_setting(message.chat.id, "welcome_text", value)
    await message.reply_text(texts.SET_WELCOME_OK.format(title=message.chat.title))


@Client.on_message(filters.command("set_tutorial") & filters.group, group=0)
async def set_tutorial(client: Client, message):
    if not await group_admin_guard(client, message):
        return
    value = _argument(message)
    if not value:
        await message.reply_text(texts.COMMAND_INCOMPLETE.format(usage="/set_tutorial &lt;url&gt;"))
        return
    await update_setting(message.chat.id, "tutorial", value)
    await message.reply_text(texts.SET_TUTORIAL_OK.format(title=message.chat.title))


@Client.on_message(filters.command("set_shortlink") & filters.group, group=0)
async def set_shortlink(client: Client, message):
    await react(message)
    if not await group_admin_guard(client, message):
        return
    parts = message.text.split()
    if len(parts) != 3:
        await message.reply_text(
            texts.COMMAND_INCOMPLETE.format(
                usage="/set_shortlink mdisklink.link 5843c3cc645f5077b2200a2c77e0344879880b3e"
            )
        )
        return
    _, url, api = parts
    if not await shortlink_service.is_valid(url, api):
        await message.reply_text(texts.SHORTLINK_INVALID)
        return
    await update_setting(message.chat.id, "url", url)
    await update_setting(message.chat.id, "api", api)
    await message.reply_text(
        texts.SET_SHORTLINK_OK.format(title=message.chat.title, url=url, api=api)
    )


@Client.on_message(filters.command("get_custom_settings") & filters.group, group=0)
async def get_custom_settings(client: Client, message):
    if not await group_admin_guard(client, message):
        return
    chat_settings = await get_settings(message.chat.id)
    fsub = ", ".join(str(item) for item in chat_settings["fsub"]) or "not set"
    await message.reply_text(
        texts.SETTINGS_SUMMARY.format(
            title=message.chat.title,
            url=chat_settings["url"] or "-",
            api=chat_settings["api"] or "-",
            template=chat_settings["template"],
            caption=chat_settings["caption"],
            welcome=chat_settings["welcome_text"],
            tutorial=chat_settings["tutorial"],
            fsub=fsub,
        ),
        reply_markup=kb.close_keyboard(),
        disable_web_page_preview=True,
        parse_mode=ParseMode.HTML,
    )


@Client.on_message(filters.command("set_fsub") & filters.group, group=0)
async def set_fsub(client: Client, message):
    if not await group_admin_guard(client, message):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text(
            texts.COMMAND_INCOMPLETE.format(usage="/set_fsub -1001234567890 -1009876543210")
        )
        return
    try:
        ids = [int(token) for token in parts[1].split()]
    except ValueError:
        await message.reply_text("Chat ids must be integers.")
        return

    titles: list[str] = []
    for chat_id in ids:
        try:
            chat = await client.get_chat(chat_id)
        except Exception as error:  # noqa: BLE001
            await message.reply_text(f"<code>{chat_id}</code> is invalid: {error}")
            return
        if chat.type != ChatType.CHANNEL:
            await message.reply_text(f"<code>{chat_id}</code> is not a channel.")
            return
        titles.append(chat.title or str(chat_id))

    await update_setting(message.chat.id, "fsub", ids)
    await message.reply_text(
        texts.SET_FSUB_OK.format(title=message.chat.title, channels="\n".join(titles)),
        parse_mode=ParseMode.HTML,
    )


@Client.on_message(filters.command("remove_fsub") & filters.group, group=0)
async def remove_fsub(client: Client, message):
    if not await group_admin_guard(client, message):
        return
    chat_settings = await get_settings(message.chat.id)
    if not chat_settings["fsub"]:
        await message.reply_text(texts.FSUB_EMPTY)
        return
    await update_setting(message.chat.id, "fsub", [])
    await message.reply_text(texts.FSUB_REMOVED)


__all__ = [
    "get_custom_settings",
    "remove_fsub",
    "set_caption",
    "set_fsub",
    "set_shortlink",
    "set_template",
    "set_tutorial",
    "set_welcome",
    "settings_cmd",
]
