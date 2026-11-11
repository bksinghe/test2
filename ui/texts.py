"""All user facing copy in one place."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config import settings

# ---------------------------------------------------------------- greetings
START_TEXT = """<b>Hey {mention}, {wish}</b>
<i>I am a powerful auto filter bot with link shortener.
Add me to your group and just send a movie or series name.</i>"""

GROUP_START_TEXT = """<b>Hey {mention}, {wish}</b>
<i>How can I help you? Send me a movie or series name.</i>"""

WELCOME_BOT_ADDED = """👋 Hello {mention},

Thank you for adding me to <b>{title}</b>. Please make me an admin so I can
filter files and delete links. 😇"""

NEW_USER = "#NewUser\n★ Name: {mention}\n★ ID: <code>{user_id}</code>"
NEW_GROUP = (
    "#NewGroup\nTitle - {title}\nID - <code>{chat_id}</code>\n"
    "Username - {username}\nMembers - <code>{members}</code>"
)

# ------------------------------------------------------------------ about
ABOUT_TEXT = """<b>🤖 {bot_name}</b>
<b>Version:</b> 6.0 (restructured)
<b>Library:</b> Pyrogram
<b>Database:</b> MongoDB
<b>Streaming:</b> {stream_status}"""

HELP_TEXT = """<b>Available help sections</b>
<i>Tip: send a command without arguments to see its usage.</i>"""

USER_COMMANDS = """<b>User commands</b>

/start - wake the bot up / open a shared file link
/id - show the current chat or user id
/plan - premium plans
/myplan - your premium status
/settings - group settings (admins only)
/manage - bulk member cleanup (admins only)"""

ADMIN_COMMANDS = """<b>Bot admin commands</b>

/stats - bot stats
/ping - latency check
/speedtest - server speed test
/index_channels - indexed channels
/index - reply to a forwarded post or channel link to index it
/delete &lt;query&gt; - delete indexed files by query
/delete_all - wipe the whole index
/broadcast &amp; /pin_broadcast - send to all users
/grp_broadcast &amp; /pin_grp_broadcast - send to all groups
/ban_user &amp; /unban_user - bot level user ban
/ban_grp &amp; /unban_grp - disable / enable a group
/users &amp; /chats - database dumps
/leave &lt;chat_id&gt; - leave a group
/invite_link &lt;chat_id&gt; - create an invite link
/set_pm_search on|off - toggle search inside private chat
/restart - restart the bot
/eval &lt;code&gt; - run python (dangerous)"""

# ----------------------------------------------------------------- search
SEARCHING = "<b><i>⚠️ <code>{query}</code> searching…</i></b>"
NOT_FOUND = """👋 Hello {mention},

I could not find <b>{query}</b> in my database. 🥲

👉 Check your spelling or try the English title.
👉 Use the instructions button for the correct request format.
👉 It might not be released yet."""

SUGGESTIONS = """👋 Hello {mention},

I could not find <b>{query}</b>. Did you mean one of these? 👇"""

INSTRUCTIONS = (
    "Movie request format\nExample: Black Adam or Black Adam 2022\n\n"
    "TV series request format\nExample: Loki S01E01\n\n"
    "Do not use symbols."
)

RESULT_FOOTER = """<b>✅ Results for:</b> <code>{query}</code>
<b>🗂 Total files:</b> {total}
<b>🗣 Requested by:</b> {mention}"""

AUTO_DELETE_NOTICE = (
    "\n\n<b>⚠️ This message will be deleted after "
    "<code>{delay}</code> to avoid copyright issues</b>"
)

PM_FILES_NOTICE = (
    "Nᴏᴛᴇ: Tʜɪs ғɪʟᴇ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ɪɴ {delay} ᴛᴏ ᴀᴠᴏɪᴅ "
    "ᴄᴏᴘʏʀɪɢʜᴛ ɪssᴜᴇs. Sᴀᴠᴇ ɪᴛ sᴏᴍᴇᴡʜᴇʀᴇ ᴇʟsᴇ."
)
FILES_GONE = (
    "Tʜᴇ ғɪʟᴇ ʜᴀs ʙᴇᴇɴ ɢᴏɴᴇ! Cʟɪᴄᴋ ᴛʜᴇ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ "
    "ᴛᴏ ɢᴇᴛ ɪᴛ ᴀɢᴀɪɴ."
)

# ------------------------------------------------------------------ gates
VERIFY_REQUIRED = "You are not verified yet. Please verify to continue. 🔐"
FSUB_REQUIRED = (
    "👋 Please join the channel(s) below and tap <i>Try again</i>. 😇"
)
VERIFIED = "✅ Verified! You can continue for {duration}."
INVALID_TOKEN = "This verification link is invalid or expired. Send /start again."
INVALID_LINK = "This link is invalid or has expired. Please search again."

# ----------------------------------------------------------------- premium
PLANS = """<b><i><u>- Available plans -</u>

- ₹30 - 1 week
- ₹50 - 1 month
- ₹120 - 3 months
- ₹220 - 6 months

<u>🎁 Premium features 🎁</u>

○ No verification needed
○ No shortlink needed
○ Direct files
○ Ad free experience
○ High speed download links
○ Unlimited movies &amp; series
○ Full admin support

✨ UPI ID - <code>{upi}</code>

Check your plan with /myplan
💢 Send a screenshot after payment
‼️ Give us some time to activate premium</i></b>"""

PREMIUM_ACTIVE = """<b>Your plan details</b>

<b>Remaining:</b> {remaining}
<b>Expires:</b> {expires}"""
PREMIUM_NONE = (
    "😢 You do not have an active premium subscription.\n\nCheck /plan"
)
PREMIUM_ADDED = "<b>Premium added for {duration}. Enjoy! 😀</b>"
PREMIUM_REMOVED = (
    "<b>Premium removed by an admin.</b>\n\nContact {owner} if this is a mistake."
)

TRIAL_GRANTED = (
    "**You can use the free trial for 5 minutes from now 😀**\n\n"
    "आप अब से 5 मिनट के लिए निःशुल्क ट्रायल का उपयोग कर सकते हैं 😀"
)
TRIAL_USED = "🤣 You already used the free trial. Please buy a plan with /plan."

# ------------------------------------------------------------------ status
STATUS = """🗃️ Total files: <code>{files}</code>
🦹 Total users: <code>{users}</code>
💬 Total chats: <code>{chats}</code>
🚀 Premium users: <code>{premium}</code>
📂 Used storage: <code>{used}</code>
🗂 Free storage: <code>{free}</code>
⏰ Uptime: <code>{uptime}</code>"""

PING = "<b>Pong!</b> <code>{latency} ms</code>"

# ------------------------------------------------------------------ errors
NOT_ADMIN = "Only bot admins can use this."
NOT_GROUP_ADMIN = "You are not an admin in this group."
ANONYMOUS_ADMIN = (
    "You are posting as an anonymous admin, so I cannot verify you. "
    "Please use this command without anonymous mode."
)
GROUP_ONLY = "Use this command in a group."
ADMIN_ONLY_BUTTON = "Bot admins only!"
NOT_FOR_YOU = "Hello {name},\nThis is not for you!"
CLOSED = "Closed!"
LINK_BLOCKED = "Links are not allowed here!"
AUTO_FILTER_OFF = "Auto filter is off here! ❌"
REQUEST_SENT = "Request sent!"
REPORT_SENT = "Report sent!"
SEARCH_EXPIRED = "This result expired. Please search again."
COMMAND_INCOMPLETE = "Command incomplete. Usage: <code>{usage}</code>"
SOMETHING_WRONG = "Something went wrong. Please try again."

# --------------------------------------------------------------- settings
SETTINGS_TITLE = "Change the settings for <b>{title}</b> as you wish. ⚙"
SET_TEMPLATE_OK = "Template updated for {title}."
SET_CAPTION_OK = "Caption updated for {title}."
SET_WELCOME_OK = "Welcome text updated for {title}."
SET_TUTORIAL_OK = "Tutorial link updated for {title}."
SET_SHORTLINK_OK = "Shortlink updated for {title}.\n\nURL: <code>{url}</code>\nAPI: <code>{api}</code>"
SHORTLINK_INVALID = "That shortlink url/api did not work. Please check again."
SET_FSUB_OK = "Force subscribe channels for {title}:\n\n{channels}"
FSUB_EMPTY = "You have not set any force subscribe channel yet."
FSUB_REMOVED = "Force subscribe channels removed."
SETTINGS_SUMMARY = """<b>Settings for {title}</b>

Shortlink URL: <code>{url}</code>
Shortlink API: <code>{api}</code>
IMDb template: <code>{template}</code>
File caption: <code>{caption}</code>
Welcome text: <code>{welcome}</code>
Tutorial: <code>{tutorial}</code>
Force channels: <code>{fsub}</code>"""

# ------------------------------------------------------------------- misc
INVALID_ID = "Give me a valid chat id."
CHAT_DISABLED = "This chat is already disabled.\nReason - <code>{reason}</code>"
CHAT_ENABLED = "Chat re-enabled."
CHAT_DISABLED_OK = "Chat disabled."
USER_BANNED = "Successfully banned {mention}."
USER_UNBANNED = "Successfully unbanned {mention}."
BANNED_NOTICE = """Sorry {mention},
my owner banned you from using me. Contact the support group for details.
Reason - <code>{reason}</code>"""
CHAT_DISABLED_NOTICE = """<b><u>Chat not allowed</u></b>

My owner restricted me from working here. Contact the support group.
Reason - <code>{reason}</code>"""
LEFT_NOTICE = """Hello friends,
my owner asked me to leave this group. Add me again from the support group.
Reason - <code>{reason}</code>"""
LEFT_OK = "✅ Left <code>{chat_id}</code>."
USAGE_LEAVE = "/leave &lt;chat_id&gt; [reason]"
USAGE_CHAT_ID = "/{command} &lt;chat_id&gt;"

DELETE_PREVIEW = "Found <b>{total}</b> files for <code>{query}</code>.\n\nDelete them?"
DELETE_NONE = "No files matched that query."
DELETE_DONE = "Deleted <b>{count}</b> files for <code>{query}</code>."
DELETE_ALL_PREVIEW = "There are <b>{total}</b> indexed files.\n\nDelete all of them?"
DELETE_ALL_DONE = "Deleted <b>{count}</b> files."
DELETE_ALL_EMPTY = "There is nothing to delete."
DELETE_CONFIRM_EXPIRED = "This delete request expired. Run the command again."

INDEX_STARTED = "<b>Indexing started…</b>"
INDEX_USAGE = "Reply to a forwarded channel post or send a t.me link."
INDEX_SKIP_PROMPT = "Send the number of messages to skip."
INDEX_SKIP_INVALID = "That is not a valid number."
INDEX_ONLY_CHANNELS = "I can only index channels."
INDEX_CONFIRM = "Index <b>{title}</b>?\nTotal messages: <code>{last_id}</code>"
INDEX_PROGRESS = """<b>Indexing {title}</b>

Received: <code>{current}</code>
Saved: <code>{saved}</code>
Duplicates: <code>{duplicates}</code>
Deleted messages: <code>{deleted}</code>
Non media: <code>{skipped}</code>
Errors: <code>{errors}</code>"""
INDEX_DONE = """<b>Indexing finished in {duration}</b>

Saved: <code>{saved}</code>
Duplicates: <code>{duplicates}</code>
Deleted messages: <code>{deleted}</code>
Non media: <code>{skipped}</code>
Errors: <code>{errors}</code>"""
INDEX_CANCELLED = "<b>Indexing cancelled.</b>\n\nSaved: <code>{saved}</code>"
INDEX_BUSY = "Another indexing job is running, please wait."

BROADCAST_STARTED = "Broadcasting to {target}…"
BROADCAST_PROGRESS = """Broadcast in progress

Target: <code>{target}</code>
Done: <code>{done} / {total}</code>
Success: <code>{success}</code>
Failed: <code>{failed}</code>"""
BROADCAST_DONE = """Broadcast finished in {duration}

Target: <code>{target}</code>
Done: <code>{done} / {total}</code>
Success: <code>{success}</code>
Failed: <code>{failed}</code>"""
BROADCAST_CANCELLED = "<b>Broadcast cancelled.</b>"

PM_SEARCH_ON = "<b>✅ PM search enabled. Users can search in private chat.</b>"
PM_SEARCH_OFF = "<b>❌ PM search disabled.</b>"
PM_SEARCH_INVALID = "<b>💔 Invalid option. Use on/off or true/false.</b>"

INLINE_BANNED = "You are banned."
INLINE_NO_RESULTS = "No results"
INLINE_RESULTS = "Results"


def greeting(now: datetime | None = None) -> str:
    """Time of day greeting in the configured timezone."""
    try:
        tz = ZoneInfo(settings.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        tz = ZoneInfo("UTC")
    now = now.astimezone(tz) if now else datetime.now(tz)
    if now.hour < 12:
        return "ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ 🌞"
    if now.hour < 18:
        return "ɢᴏᴏᴅ ᴀғᴛᴇʀɴᴏᴏɴ 🌗"
    return "ɢᴏᴏᴅ ᴇᴠᴇɴɪɴɢ 🌘"


__all__ = [name for name in dir() if name.isupper()] + ["greeting"]
