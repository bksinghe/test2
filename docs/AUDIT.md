# 🔍 Auto Filter Bot — Deep Research & Restructure Report

> **Status:** ✅ this audit has been implemented. The legacy `plugins/`,
> `database/`, `info.py`, `utils.py` and `Script.py` modules are gone and the
> code now lives in the layered structure described in
> [`../README.md`](../README.md). The numbers below describe the *old* code and
> are kept as the record of what was found and why it was rewritten.

> **Repo:** `bksinghe/test2` · **Branch:** `arena/480e413f-test2` · **Commit base:** `ee81179`
> **Type:** Telegram Auto-Filter + Link-Shortener + Premium + Streamer bot (EvaMaria / Auto-Filter family ka fork)
> **Stack:** Python 3.11 · Pyrofork 2.3.43 (Pyrogram fork) · MongoDB (motor + umongo) · aiohttp web server · Docker / Heroku
> **Branding:** "UncutFlix" / "DesiXCloud" / "YourX" (v5.0) — sab hardcoded hai

---

## 0. Snapshot (numbers pehle)

| Metric | Value |
|---|---|
| Total Python LOC | **3,955** (`plugins/` = 2,576 = **65%**) |
| Total files | 21 py + 1 html + 1 css + config files |
| Biggest file | `plugins/pm_filter.py` — **1,073 lines** (**27%** of Python code) |
| 2nd biggest | `plugins/commands.py` — **694 lines** |
| Registered handlers | **57** (44 message, 11 callback, 1 inline, 1 chat_member_updated) |
| Commands (usable) | **41** (+1 commented out) |
| Distinct `callback_data` values | **38** |
| MongoDB collections | **5** (`Files`, `Users`, `Groups`, `uersz`, `bot_id`) |
| Env variables read | **47** (9 mandatory → missing par `exit()`, + invalid flag value par `exit()`) |
| Tests | **0** |
| CI / lint config | **0** |
| README content | **1 byte** (khali) |
| `.gitignore` | **nahi hai** |
| Dead / unreachable code | **~120 lines + 389 lines CSS** |
| Duplicate logic | **~450 lines** (settings keyboard, search pages, admin checks) |
| License | GPL-3.0 |

---

## 1. Architecture — kaise chalta hai

```
bot.py  (entrypoint)
  ├─ uvloop.install(), Bot(Client) with plugins={"root": "plugins"}
  ├─ start():  temp.START_TIME → banned users/chats load → Mongo ping
  │            → super().start() → restart.txt handling → temp.ME/U_NAME/B_NAME
  │            → Media.ensure_indexes()
  │            → aiohttp TCPSite on 0.0.0.0:PORT   ← web/stream_routes.py
  │            → LOG_CHANNEL "Restarted!" → BIN_CHANNEL test → ADMINS DM
  └─ app.run()
        │
        ├── plugins/  (Pyrogram auto-load, ALPHABETICAL order:
        │              banned → broadcast → channel → commands → eval →
        │              group_management → index → inline → misc →
        │              p_ttishow → pm_filter)
        ├── database/  (ia_filterdb = media index, users_chats_db = users/groups/settings/premium)
        ├── utils.py   (temp state, settings cache, IMDb, shortlink, verify, broadcast helpers)
        ├── info.py    (env config; missing var = print + exit())
        ├── Script.py  (saare user-facing texts — hardcoded Hinglish/Unicode-styled)
        └── web/       (index route `/`, `/watch/{id}` HTML player, `/download/{id}` Range streaming)
```

**Request flow (group search):**

```
user text (group)
  → filters.group & text  →  group_search()
      ├─ bot admin check
      ├─ new chat? → LOG_CHANNEL notify + db.add_chat()
      ├─ settings = get_settings(chat)   [in-memory cache → Mongo]
      ├─ auto_filter OFF → "Auto Filter Off!" + 5s delete
      ├─ "@admin" → forward to all admins + hidden mentions
      ├─ link detected → delete message + "Links not allowed here!"
      ├─ "#request" → LOG_CHANNEL + "Request sent!"
      └─ else → "searching..." → auto_filter()
                   ├─ get_search_results() → Files collection regex
                   ├─ mode: links (URL list) ya buttons
                   ├─ languages / quality filters, pagination (MAX_BTN)
                   ├─ shortlink gate (non-premium)
                   ├─ IMDb poster + template caption (optional)
                   └─ auto_delete → sleep(DELETE_TIME) → delete
```

---

## 2. File-by-file map

| File | LOC | Role | Notes |
|---|---|---|---|
| `bot.py` | 134 | Entrypoint, Client subclass, lifecycle, `iter_messages` | 1 dead commented block (67-69) |
| `info.py` | 137 | Env config + `is_enabled()` + IP check + URL normalise | 21 vars pe hard `exit()` |
| `utils.py` | 256 | `temp` state, settings cache, IMDb, verify, shortlink, broadcast helpers, formatters | Blocking IMDb calls |
| `Script.py` | 151 | All texts (`START_TXT`, `IMDB_TEMPLATE`, `PREMIUM_PLAN_TEXT`…) | 3 texts unreachable |
| `database/ia_filterdb.py` | 145 | umongo `Media` model, save/search/delete, file-id pack/unpack | `save_file` semantik issues |
| `database/users_chats_db.py` | 240 | Users, Groups, settings, verify, premium, pm-search flag | **5 collections, 2 user collections** |
| `plugins/commands.py` | 694 | `/start` deep-links + 19 admin/group commands + premium + fsub | Sabse mixed bag |
| `plugins/pm_filter.py` | 1073 | PM + group search, results UI, 9 callbacks, `auto_filter`, spell-check | **Refactor ka #1 target** |
| `plugins/p_ttishow.py` | 238 | Welcome, restart, leave, ban/unban user+chat, users/chats list | "ttishow" = leftover name |
| `plugins/broadcast.py` | 96 | User/group broadcast + pin variants + cancel | |
| `plugins/index.py` | 128 | Manual channel indexing (forward/link + skip) + progress + cancel | |
| `plugins/channel.py` | 20 | Auto-index `INDEX_CHANNELS` media | |
| `plugins/inline.py` | 70 | Inline search (`@bot query`) with cached documents | |
| `plugins/banned.py` | 44 | Banned user / disabled chat custom filters | Filter bug |
| `plugins/group_management.py` | 95 | `/manage`, ban/mute/unban/unmute | `ban` wrong chat bug |
| `plugins/misc.py` | 65 | `/id`, `/speedtest` | `id` crash bug |
| `plugins/eval.py` | 53 | `/eval` (exec, admin only) | RCE surface |
| `web/__init__.py` | 8 | aiohttp app + routes | |
| `web/stream_routes.py` | 77 | `/`, `/watch/{id}`, `/download/{id}` (HTTP Range) | mime fallback bug |
| `web/utils/custom_dl.py` | 212 | Telegram DC session + chunk streaming | 1 unused fn |
| `web/utils/render_template.py` | 20 | watch.html render | only video MIME |
| `web/template/watch.html` | 77 | Plyr player page | references missing CSS |
| `web/template/style.css` | 389 | Styling | **never served (404)** |

---

## 3. Feature catalog — chhoti se chhoti cheez

### 3.1 Core search & filter
1. **Group auto-filter** — group me plain text → DB regex search → results (`pm_filter.py:38`).
2. **PM search** — bot DM me text → results (`pm_filter.py:19`).
3. **PM search ON/OFF globally** — `/set_pm_search on|off`, DB `bot_id` collection (`commands.py:622`).
4. **Auto-filter ON/OFF per group** — setting toggle (`commands.py:275` keyboard, `pm_filter.py:46`).
5. **Regex search modes** — single word = boundary match; multi-word = `.*[\s\.\+\-_]` join (`ia_filterdb.py:54`).
6. **Caption search** — `USE_CAPTION_FILTER=True` → file_name + caption dono me search (`ia_filterdb.py:68`).
7. **Pagination** — `MAX_BTN` (default 10) results/page, BACK/NEXT + page counter (`pm_filter.py:118`).
8. **Language filter** — buttons se `LANGUAGES` me se choose, filename substring match (`pm_filter.py:195, 221`).
9. **Quality filter** — `QUALITY` list (360p…2160p) (`pm_filter.py:208, 399`).
10. **Result page mode** — `LINK_MODE=True` → clickable links list; else inline buttons (`settings['links']`).
11. **"Send all"** — ek click me saare results PM me (shortlink gate ke saath) (`commands.py:127`).
12. **Spell check / suggestions** — 0 results par IMDb se possible titles → buttons → re-search (`pm_filter.py:1030, 469`).
13. **Instructions popup** — movie/series request format alert (`pm_filter.py:594`).
14. **Google fallback button** — no result par "Search Google" link (`pm_filter.py:1030`).
15. **Inline mode search** — `@bot <query>` with `CACHE_TIME`, personal results, next_offset (`inline.py`).
16. **Timestamped "searching…" placeholder** jo result me edit hota hai (UX).
17. **Natural sort by newest** — `sort('$natural', -1)` (`ia_filterdb.py:75`).

### 3.2 Premium / monetisation
18. **Premium plans page** — `/plan` + `?start=plans` + `buy_premium` callback → QR photo + plans text (`Script.PREMIUM_PLAN_TEXT`).
19. **`/myplan`** — remaining time + expiry; warna free-trial/buy buttons (`commands.py:599`).
20. **5-minute free trial** — one-time per user, `has_free_trial` flag (`db.give_free_trail`).
21. **`/add_premium user_id time`** — 1s/1min/1hour/1day/1month/1year parser (`utils.get_seconds`).
22. **`/remove_premium user_id`** — expiry = now+1s + DM notification.
23. **Premium bypasses** — verification skip, force-sub skip, shortlink skip, `protect_content=False`, no watermark waits.
24. **Payment QR + UPI ID** — `PAYMENT_QR`, `OWNER_UPI_ID` env.
25. **Premium count in /stats**.

### 3.3 Verification (shortlink-based)
26. **Token-based verify** — random 10-char token, stored per user, deep link `?start=verify_<token>` (`commands.py:79`).
27. **Shortlink wrapping** — `Shortzy` converts verify URL (`utils.get_shortlink`).
28. **Verify expiry** — `VERIFY_EXPIRE` (default 86400s), auto-unverify on `/start`.
29. **Verify tutorial button** — `VERIFY_TUTORIAL`.
30. **Post-verify "Get File" button** — original file link resume (`commands.py:88-98`).
31. **Force-subscribe (fsub)** — multiple channels per group, join check + invite buttons + "Try Again" (`commands.py:646`, `pm_filter.py:556`).
32. **`/remove_fsub`** — clear channels.

### 3.4 File delivering
33. **Single file deliver** — caption template + size + stream/close buttons (`commands.py:173`).
34. **All-files deliver** — loop `send_cached_media` + count message.
35. **PM auto-delete of files** — `PM_FILE_DELETE_TIME` (3600s) + "get file again" button (`get_del_file`, `get_del_send_all_files`).
36. **Custom caption template** — `/set_caption` with `{file_name} {file_size} {file_caption}` (`commands.py:330`).
37. **Content protection** — non-premium files `protect_content=True`.
38. **Group auto-delete of result message** — `DELETE_TIME` + warning line (`settings['auto_delete']`).
39. **Shortlink before file** — non-premium ko shortlink page (`commands.py:179`).
40. **"How to open link" tutorial button** — per-group `tutorial` (default `TUTORIAL`).

### 3.5 Streaming (web)
41. **`/watch/{message_id}`** — HTML page with Plyr player + marquee filename.
42. **`/download/{message_id}`** — Range/206 support, chunked from Telegram DC.
43. **`/`** — simple branding page ("YourX").
44. **Stream buttons in results** — "Watch And Download" (`commands.py`, `pm_filter.py:527`).
45. **Per-group Stream ON/OFF** setting `is_stream`.
46. **Custom TG DC media session** reuse (`custom_dl.py:42`), `ExportAuthorization` retry x3.
47. **Auto file-type handling** — video → player; baaki → "not streamable".

### 3.6 Indexing
48. **Auto-index** — `INDEX_CHANNELS` me naye media automatically `save_file()` (`channel.py`).
49. **Manual index by forwarded message / channel link** — admin DM me forward ya `https://t.me/...` link bheje (`index.py:30`).
50. **Skip count prompt** — "Send skip message number." via `bot.listen()`.
51. **Confirmation keyboard** — YES / CLOSE.
52. **Live progress** every 30 messages + CANCEL button (`index.py:95-100`).
53. **Final report** — saved/duplicate/deleted/non-media/unsupported/errors/badfiles.
54. **Global lock** — ek time par ek indexing (aur ek hi global `temp.CANCEL`).

### 3.7 Group settings & customisation
55. **`/settings` panel** — 8 toggles (Auto Filter, IMDb, Spell Check, Auto Delete, Welcome, Shortlink, Result Page, Stream). *(file_secure nahi hai UI me.)*
56. **`/set_template`** — custom IMDb caption template per group.
57. **`/set_shortlink url api`** — validated via live API call.
58. **`/set_welcome`** — welcome text with `{mention}`, `{title}`.
59. **`/set_tutorial`** — per-group tutorial URL.
60. **`/get_custom_settings`** — dump of group config.
61. **Anonymous-admin guard** — sab group commands "You are Anonymous admin…" dete hain.
62. **Group-admin guard** — `is_check_admin()` (ADMINISTRATOR/OWNER) har command me.

### 3.8 Admin / ops
63. **`/stats`** — files, users, chats, premium, DB used/free (512MB assume!), uptime.
64. **`/index_channels`** — listed channels + count.
65. **`/delete <query>`** — count + YES confirm → Mongo delete (`delete_files`).
66. **`/delete_all`** — drop entire Files collection.
67. **`/broadcast`, `/pin_broadcast`** — reply-based, progress every 20, cancel button.
68. **`/grp_broadcast`, `/pin_grp_broadcast`** — same for groups.
69. **`/restart`** — writes `restart.txt`, `os.execl`; restart par "Restarted Successfully!" edit.
70. **`/ping`** — latency *(broken, see §10)*.
71. **`/id`** — user/group/channel ID *(reply path broken)*.
72. **`/speedtest`** — full server/client report + share image.
73. **`/eval`** — arbitrary Python exec (admin).
74. **`/users` / `/chats`** — full dumps, >4096 chars par `.txt` file.
75. **`/invite_link <chat_id>`** — create invite link.
76. **`/leave <chat_id> [reason]`** — DM + leave.
77. **`/ban_grp`, `/unban_grp`** — disable/enable chat + add/remove from `temp.BANNED_CHATS`.
78. **`/ban_user`, `/unban_user`** — ban + reason, DM, `temp.BANNED_USERS` live update.
79. **Startup validation** — LOG_CHANNEL admin check, BIN_CHANNEL ensure; fail → `exit()`.

### 3.9 Moderation (`group_management.py`)
80. **`/manage`** — 4 buttons: Unmute All, Unban All, Kick Muted, Kick Deleted Accounts.
81. **`/ban`** — reply/username/id se ban *(galat chat me ban karta hai)*.
82. **`/mute`** — `ChatPermissions()` all-false restrict.
83. **`/unban` / `/unmute`** — unban member.
84. **`@admin` mention report** — DM to all admins with user/group/link.
85. **Anti-link** — non-admin ke messages me link/@username → delete + warning.
86. **`#request`** — LOG_CHANNEL me request + "Request sent!".

### 3.10 Welcome / greetings
87. **Bot add karne par greeting photo** + update/support buttons + auto-add group to DB.
88. **New member welcome** — per-group `welcome` toggle + `welcome_text` (`p_ttishow.py:13`).
89. **`get_wish()`** — Asia/Colombo timezone ke hisaab se Good morning/afternoon/evening (`utils.py:218`).

### 3.11 Ban plumbing
90. **Custom filters** `banned_user` / `disabled_group` (`banned.py`) + banned message with reason + support button.
91. **Disabled group → bot leaves** after pinned notice.

### 3.12 UI micro-features
92. **Random emoji reaction** on ~12 commands (`REACTIONS` list, fallback ⚡️).
93. **Random photo** from `PICS` for /start, fsub gate, bot-add greeting.
94. **`close_data`** — delete message (+ replied message).
95. **Multi-page bottom nav** — BACK / page counter / NEXT.
96. **"Buy" button** injected in filtered result pages.
97. **Spoiler** in help text, HTML parse mode everywhere.
98. **`buttons` callback** — page counter tap par "⚠️" toast.
99. **Help → User/Admin command split** (admin-only guard).
100. **`about` → `stats`**, `earn → howshort` *(earn unreachable)*, `owner` *(unreachable)*.

---

## 4. Command reference — poora list (41)

**Legend:** 👤=any user · 🛡=group admin · 👑=bot admin (`ADMINS`) · 📁=group only · 💬=PM only

| # | Command | Who | Scope | File:line | Kaam |
|---|---|---|---|---|---|
| 1 | `/start` | 👤 | any | `commands.py:16` | Welcome photo + deep-link router (sabse bada handler) |
| 2 | `/settings` | 🛡 | 📁 | `commands.py:259` | 8 toggles ka inline panel |
| 3 | `/set_template` | 🛡 | 📁 | `commands.py:311` | IMDb caption template |
| 4 | `/set_caption` | 🛡 | 📁 | `commands.py:330` | File caption template |
| 5 | `/set_shortlink <url> <api>` | 🛡 | 📁 | `commands.py:349` | Shortener config + live validate |
| 6 | `/get_custom_settings` | 🛡 | 📁 | `commands.py:377` | Config dump |
| 7 | `/set_welcome` | 🛡 | 📁 | `commands.py:410` | Welcome text |
| 8 | `/set_tutorial` | 🛡 | 📁 | `commands.py:478` | Tutorial URL |
| 9 | `/set_fsub <id…>` | 🛡 | 📁 | `commands.py:646` | Force-sub channels |
| 10 | `/remove_fsub` | 🛡 | 📁 | `commands.py:677` | Clear force-sub |
| 11 | `/manage` | 🛡 | 📁 | `group_management.py:6` | Bulk moderation menu |
| 12 | `/ban` | 🛡 | 📁 | `group_management.py:20` | Ban user *(bug)* |
| 13 | `/mute` | 🛡 | 📁 | `group_management.py:46` | Restrict user |
| 14 | `/unban` | 🛡 | 📁 | `group_management.py:72` | Unban |
| 15 | `/unmute` | 🛡 | 📁 | `group_management.py:72` | Unmute (same handler) |
| 16 | `/id` | 👤 | any | `misc.py:8` | Chat/user ID *(reply bug)* |
| 17 | `/ping` | 👤 | any | `commands.py:521` | Latency *(always crash)* |
| 18 | `/plan` | 👤 | any | `commands.py:585` | Premium plans + QR |
| 19 | `/myplan` | 👤 | any | `commands.py:599` | Subscription status |
| 20 | `/stats` | 👑 | any | `commands.py:239` | Full bot stats |
| 21 | `/index_channels` | 👑 | any | `commands.py:223` | Indexed channel list |
| 22 | `/delete <query>` | 👑 | any | `commands.py:433` | Delete indexed files |
| 23 | `/delete_all` | 👑 | any | `commands.py:458` | Drop all files |
| 24 | `/add_premium <id> <time>` | 👑 | any | `commands.py:528` | Grant premium |
| 25 | `/remove_premium <id>` | 👑 | any | `commands.py:556` | Revoke premium |
| 26 | `/set_pm_search on\|off` | 👑 | 💬 | `commands.py:622` | Global PM search |
| 27 | `/broadcast` | 👑 | reply | `broadcast.py:21` | DM all users |
| 28 | `/pin_broadcast` | 👑 | reply | `broadcast.py:21` | Same + pin |
| 29 | `/grp_broadcast` | 👑 | reply | `broadcast.py:59` | All groups |
| 30 | `/pin_grp_broadcast` | 👑 | reply | `broadcast.py:59` | Same + pin |
| 31 | `/restart` | 👑 | any | `p_ttishow.py:40` | Process restart |
| 32 | `/leave <chat_id> [reason]` | 👑 | any | `p_ttishow.py:47` | Leave group |
| 33 | `/ban_grp <chat_id> [reason]` | 👑 | any | `p_ttishow.py:77` | Disable group |
| 34 | `/unban_grp <chat_id>` | 👑 | any | `p_ttishow.py:113` | Enable group |
| 35 | `/invite_link <chat_id>` | 👑 | any | `p_ttishow.py:131` | Create invite |
| 36 | `/ban_user <id> [reason]` | 👑 | any | `p_ttishow.py:146` | Ban from bot |
| 37 | `/unban_user <id>` | 👑 | any | `p_ttishow.py:175` | Unban |
| 38 | `/users` | 👑 | any | `p_ttishow.py:200` | User dump / .txt |
| 39 | `/chats` | 👑 | any | `p_ttishow.py:221` | Group dump / .txt |
| 40 | `/speedtest` | 👑 | any | `misc.py:24` | Network test |
| 41 | `/eval <code>` | 👑 | any | `eval.py:9` | Python exec |
| — | `/telegraph` | — | — | `commands.py:497` | **COMMENTED OUT** (code + imports bache hue) |

### 4.1 📌 Documentation mismatches (Script.py)
- `ADMIN_COMMAND_TXT` me **`/index`** likha hai — aisa koi command nahi hai (index forwarded message se hota hai).
- `HOW_TXT` me **`/get_shortlink`** likha hai — actual command `/get_custom_settings` hai.
- `USER_COMMAND_TXT` me missing: `/plan`, `/myplan`, `/manage`, `/ban`, `/mute`, `/unban`, `/unmute`, `/ping`, `/speedtest`, `/eval`, `/add_premium`, `/broadcast…` (admin list me bhi `/eval`, `/speedtest`, `/set_*` missing).
- `START_TXT` claims "Version 5.0" per `MY_ABOUT_TXT`, aur bot ko "PowerFul Auto Filter" bolta hai — branding sirf Script.py me.
- `/help` ya `/about` **command** exist nahi karte — sirf inline callback buttons.

---

## 5. Deep-link (`?start=`) router — `commands.py:16-215`

| Payload | Matched at | Behaviour |
|---|---|---|
| *(none)* / `start` | `:57` | Main /start photo + 4 buttons |
| `plans` | `:64` | Premium QR + plans |
| `verify_<token>` | `:79` | Token check → verified + "Get File" button |
| `all_<grp_id>_<key>` | `:127` | Saare files send + auto-delete timer |
| `file_<grp_id>_<file_id>` | `:173` | Single file (shortlink gate) |
| `shortlink_<grp>_<file_id>` | `:173` | Single file bypassing shortlink |
| `inline_verify` | `:102` | Verify (no resume link) — **verified user par crash** |
| **anything else** | `:110` | `int(mc.split("_",2)[1])` → crash / weird behaviour |

Order of gates for file links: verify → fsub → shortlink → deliver → auto-delete.

---

## 6. Callback map (38 values)

| callback_data | Handler (file:line) | Status |
|---|---|---|
| `next_…` | `pm_filter.py:118` | ✅ pagination |
| `languages#…`, `quality#…` | `:195`, `:208` | ✅ filter menus |
| `lang_search#…`, `lang_next#…` | `:221`, `:277` | ✅ |
| `qual_search#…`, `qual_next#…` | `:353`, `:399` | ✅ |
| `spolling#…` | `:469` | ✅ spell suggestion |
| `file#…` | `:505` | ✅ open file via deep link |
| `get_del_file#…` | `:517` | ✅ re-send deleted file |
| `get_del_send_all_files#…` | `:522` | ✅ re-send all |
| `stream#…` | `:527` | ✅ watch/download links **(bin me duplicate re-upload)** |
| `get_trail` | `:543` | ✅ 5-min trial |
| `checksub#…` | `:556` | ✅ fsub retry |
| `unmuteme#…` | `:570` | ❌ **orphan — koi button nahi banata** |
| `close_data` | `:493` | ✅ |
| `buttons` | `:591` | ✅ page-counter toast |
| `instructions` | `:594` | ✅ |
| `start`, `about`, `help`, `user_command`, `admin_command` | `:597–:716` | ✅ nav |
| `stats` | `:627` | ✅ (admin) |
| `owner` | `:643` | ❌ **orphan — no entry point** |
| `earn` | `:659` | ❌ **orphan (only reachable from `howshort` Back, which is unreachable)** |
| `howshort` | `:672` | ❌ effectively unreachable |
| `setgs#…` | `:718` | ✅ settings toggle (keyboard duplicated) |
| `delete_all` | `:767` | ✅ |
| `delete_…` | `:773` | ✅ *(query me `#` ho to split tootega)* |
| `send_all#…` | `:783` | ✅ |
| `unmute_all_members` | `:793` | ✅ |
| `unban_all_members` | `:814` | ✅ |
| `kick_muted_members` | `:835` | ✅ |
| `kick_deleted_accounts_members` | `:856` | ✅ |
| `buy_premium` | `:878` | ✅ |
| `index#yes/cancel#…` | `index.py:13` | ✅ indexing |
| `broadcast_cancel#users/groups` | `broadcast.py:11` | ✅ |

---

## 7. Database schema (5 collections)

```
Files            (umongo model Media; index on file_name)
  _id          = packed file_id (base64 of struct <iiqq>)
  file_name    = normalised ("_" "-" "." "+" → space)
  file_size    = int
  caption      = str | None

Users            (users_chats_db.col)  ← ban + verify
  id, name, ban_status{is_banned, ban_reason}, verify_status{is_verified,
  verified_time, verify_token, link, expire_time}

Groups           (users_chats_db.grp)
  id, title, chat_status{is_disabled, reason}, settings{...16 keys...}

uersz            (users_chats_db.users)  ← PREMIUM (naam typo!)
  id, expiry_time, has_free_trial

bot_id           (users_chats_db.botcol)
  id (bot id), bot_pm_search (bool)
```

**settings keys (per group):** `auto_filter`, `file_secure` ⚠️(never read), `imdb`, `spell_check`, `auto_delete`, `welcome`, `welcome_text`, `template`, `caption`, `url`, `api`, `shortlink`, `tutorial`, `links`, `fsub`, `is_stream`.

**Design smell:** users do ek collection me hain (`Users`) par premium doosri me (`uersz`). `/users` sirf `Users` padhta hai; naya premium user `uersz` me alone ho sakta hai.

---

## 8. Config / env matrix (47 vars)

**Required (missing = bot `exit()`):** `API_ID`, `API_HASH`, `BOT_TOKEN`, `ADMINS`, `LOG_CHANNEL`, `SUPPORT_GROUP`, `DATABASE_URL`, `BIN_CHANNEL`, `URL`.
> ⚠️ `BIN_CHANNEL` + `URL` bhi mandatory hain **chahe `IS_STREAM=False`** ho — deployment friction.

| Var | Default | Kaam |
|---|---|---|
| `PORT` | 80 | aiohttp bind |
| `PICS` | 5 telegra.ph URLs | start/greeting photos |
| `INDEX_CHANNELS` | "" | auto-index channels |
| `DATABASE_NAME` / `COLLECTION_NAME` | Cluster0 / Files | Mongo |
| `SUPPORT_LINK`, `UPDATES_LINK`, `FILMS_LINK`, `TUTORIAL`, `VERIFY_TUTORIAL`, `OWNER_USERNAME` | UncutFile/YourX/… | buttons |
| `DELETE_TIME` | 3600 | group result auto-delete |
| `PM_FILE_DELETE_TIME` | 3600 | PM file auto-delete |
| `CACHE_TIME` | 300 | inline cache |
| `MAX_BTN` | 10 | results/page |
| `LANGUAGES` | `FreeMasx UnTuch Sky MyDesi Hindi Parn App XHamster` | language filters |
| `QUALITY` | 360p…2160p | quality filters |
| `IMDB_TEMPLATE`, `FILE_CAPTION`, `WELCOME_TEXT` | Script.py | text defaults |
| `SHORTLINK_URL`, `SHORTLINK_API` | **hardcoded `mdiskshortner.link` + API key** 🔴 | secrets in repo |
| `VERIFY_EXPIRE` | 86400 | verification validity |
| `USE_CAPTION_FILTER` | True | caption search |
| `IS_PM_SEARCH`, `IS_VERIFY`, `AUTO_DELETE`, `WELCOME`, `PROTECT_CONTENT`, `LONG_IMDB_DESCRIPTION`, `LINK_MODE`, `AUTO_FILTER`, `IMDB`, `SPELL_CHECK`, `SHORTLINK`, `IS_STREAM` | mixed | feature flags |
| `PAYMENT_QR`, `OWNER_UPI_ID` | telegra.ph / sampleupi@upi | payment |
| `URL`, `BIN_CHANNEL` | — | streaming |

**Leaks / risks:** `SHORTLINK_API` default key, `PAYMENT_QR` image, owner personal info in `Script.MY_OWNER_TXT` ("Amit Sharma, @RjdTv, Hindustan").

---

## 9. 🗑 Dead code inventory

| # | Item | Location | Lines | Verdict |
|---|---|---|---|---|
| 1 | `/telegraph` command + `telegraph()`, `upload_file`, `os` imports | `commands.py:497-520` | ~24 | Handler commented, code alive → delete ya `telegraph.py` bana ke enable karo |
| 2 | `owner` callback + `MY_OWNER_TXT` | `pm_filter.py:643`, `Script.py:10` | ~18 | Koi button `owner` nahi bhejta |
| 3 | `earn` callback + `EARN_TXT` | `pm_filter.py:659`, `Script.py:40` | ~14 | Koi entry point nahi |
| 4 | `howshort` callback + `HOW_TXT` | `pm_filter.py:672`, `Script.py:52` | ~12 | Sirf dead `earn` se pahunchta hai |
| 5 | `unmuteme` callback | `pm_filter.py:570-589` | ~20 | Koi button generate nahi karta (mute flow me join-mute nahi hai) |
| 6 | `file_secure` setting + `PROTECT_CONTENT` env | `users_chats_db.py:12`, `info.py:102` | 2 | Setting save hoti hai, **kahin padhi nahi jaati** |
| 7 | `get_all_chats_count()` | `users_chats_db.py:236` | 3 | Sirf commented code me use |
| 8 | Commented migration loop | `bot.py:67-69` | 3 | Delete |
| 9 | `download_as_bytesio()` | `web/utils/custom_dl.py:173-212` | 40 | Koi caller nahi |
| 10 | `web/template/style.css` | 389 lines | 389 | watch.html link karta hai par **koi static route nahi** → 404 |
| 11 | `if 'hindi' in … return auto_filter` duplicate branch | `pm_filter.py:26-30` | 3 | Dono branch same hi karti hain |
| 12 | `badfiles` counter | `index.py:83,100,128` | — | Kabhi increment nahi hota (report me 0) |
| 13 | `file_name` unused var | `index.py:117` | 1 | Remove |
| 14 | `Info.append({...})` on dict | `users_chats_db.py:152-158` | 7 | Unreachable + galat API (dict me append nahi) |
| 15 | `username` unused, `time` shadow | `bot.py:65,129` | 2 | Cleanup |
| 16 | Unused imports | `pm_filter.py:8` (SUPPORT_LINK, UPDATES_LINK), `ia_filterdb.py:1` (logging), `users_chats_db.py:3` (time) | 3 | pyflakes clean karo |
| 17 | `media.file_type` set only in `channel.py`, used nowhere | `channel.py:18` | 1 | Dead attr |
| 18 | `temp.B_NAME` | `bot.py:64` | 1 | Set hota hai, padha nahi jaata |
| 19 | `info.is_valid_ip` | `info.py:15` | 7 | Sirf `URL` validation me (kept) |
| 20 | `PORT` + Docker `CMD python bot.py` | — | — | Theek hai, bas procfile worker vs web (Heroku) mismatch |

**Memory leaks (dead-ish, dangerous):** `BUTTONS`, `CAP` (module dicts), `temp.FILES`, `temp.SETTINGS`, `temp.VERIFICATIONS` — koi eviction nahi. Har search/verify entries permanently RAM me.

---

## 10. 🐞 Bugs & broken features (priority order)

### P0 — turant tuta hua

| # | Bug | Location | Asar |
|---|---|---|---|
| 1 | `time_now.monotonic()` — `time_now` `time` function hai | `commands.py:523,525` | **`/ping` hamesha `AttributeError`** |
| 2 | `replied_to_msg = bool(...)` phir `.chat.title` | `misc.py:11-13` | **`/id` reply par `AttributeError`** |
| 3 | `ban_chat_member(message.from_user.id, user_id)` — group ki jagah admin ki DM | `group_management.py:40` | **`/ban` kaam nahi karta** |
| 4 | `int(mc.split("_", 2)[1])` bina guard | `commands.py:110` | `/start foo` ya verified user ka `inline_verify` → **`ValueError`/`IndexError`** |
| 5 | `default_setgs` / `default_verify` shared mutable dict | `users_chats_db.py:10,29` | Ek group ka setting change **saare naye groups** me chala jaata hai; verify dict bhi mutate hota hai (`utils.py:135-142`) |
| 6 | `banned_users` filter: `(from_user is not None or not sender_chat) and from_user.id` | `banned.py:8-13` | Channel post par **`AttributeError`**; logic bhi ulta |
| 7 | `web/stream_routes.py:61` `mime_type = f"{mimetypes.guess_type(...)}"` | `web/stream_routes.py:60-61` | Content-Type me tuple string → **browser download/stream break** |
| 8 | `watch.html` `href="style.css"` par koi static route nahi | `web/template/watch.html:9`, `web/stream_routes.py` | **CSS 404** (389 lines dead) |
| 9 | `verify_status['expire_time']` old records me `0` (int) | `commands.py:42` | `is_verified=True` + `0` → datetime vs int `TypeError` |
| 10 | Broadcast me `time_taken` loop ke baad bhi use | `broadcast.py:56, 94`, `index.py:128` | Empty list par **`NameError`** |

### P1 — feature galat / risky

| # | Bug | Location | Asar |
|---|---|---|---|
| 11 | `stream` callback har click par file **BIN_CHANNEL me dobara** bhejta hai | `pm_filter.py:527-534` | Bin channel spam + storage duplicate |
| 12 | `welcome` condition `not message.old_chat_member` | `p_ttishow.py:15` | Pyrogram join events me `old_chat_member` usually `LEFT` hota hai → **welcome kabhi na bheje** (verify karna) |
| 13 | `broadcast_messages` / `groups_broadcast_messages` kisi bhi exception par user/chat **delete** | `utils.py:145-172` | Network blip = **user data loss** |
| 14 | Group me `/start` par user DB me add nahi hota (early `return`) | `commands.py:30-38` | Broadcast sirf PM users tak; group users ka koi record nahi |
| 15 | `delete_all` collection drop karta hai → **index gayab** restart tak | `pm_filter.py:767-771` | Search slow kharab |
| 16 | `delete_<query>` — `#` ya `_` wale query par split tootega | `commands.py:433-455`, `pm_filter.py:773` | Delete fail |
| 17 | IMDb + `is_subscribed` blocking sync I/O async handler me | `utils.py:44-119`, `utils.py:30` | **Event loop block** (bot freeze) |
| 18 | `get_search_results` language path **poora cursor** iterate karta hai | `ia_filterdb.py:77-84` | Bade DB par latency |
| 19 | PM search bina `filters.regex` ke — forwarded/photo captions bhi match | `pm_filter.py:18` | Unwanted searches |
| 20 | `db` me **do user collections** (`Users`, `uersz`) | `users_chats_db.py:37-41` | Inconsistent premium/ban state |
| 21 | `/eval` exec, koi sandbox nahi | `eval.py` | Admin token leak = full RCE |
| 22 | `open('restart.txt','w+')` + `os.execl` bina cleanup | `p_ttishow.py:40-45` | Crash loop par file atak sakti hai |
| 23 | `get_settings()` `temp.SETTINGS` cache kabhi invalid nahi hota (multi-instance me stale) | `utils.py:174-185` | Multi-worker par galat settings |
| 24 | `SUPPORT_GROUP` special-case me result fir bhi `FILMS_LINK` bhejta hai, `auto_filter` nahi | `pm_filter.py:60-67` | Dead-end UX |
| 25 | `is_subscribed` me `chat.invite_link` `None` ho sakta hai | `utils.py:30-42` | Button `url=None` → error |
| 26 | `get_poster` `bulk=True` par sirf pehli list return, `spoll` flow me title-only search | `utils.py:70-72`, `pm_filter.py:469` | Spell-check kamzor |

### P2 — polish / correctness

| # | Item | Location |
|---|---|---|
| 27 | `/settings` label "Auto Delete" par value `DELETE_TIME` dikhta hai — confusion | `commands.py:289` |
| 28 | `file_secure` toggle UI me nahi hai (feature adhoora) | settings keyboard |
| 29 | `/stats` free storage hardcoded `536870912` (512 MB) — galat numbers | `commands.py:255`, `pm_filter.py:635` |
| 30 | `get_seconds()` unknown unit par `0` (silently invalid) | `utils.py:230-256` |
| 31 | `save_file` `caption=None` → string `"None"` DB me | `ia_filterdb.py:33` |
| 32 | `Media.ensure_indexes()` sirf startup par; drop ke baad nahi | `bot.py:60` |
| 33 | `index.py` lock global + `temp.CANCEL` global | `index.py:11, 91` |
| 34 | `pm_filter` `close_data` user ka original message bhi delete karta hai | `pm_filter.py:493-504` |
| 35 | `Script` me Unicode "sᴍᴀʟʟ ᴄᴀᴘs" everywhere — search/UX me copy-paste mushkil | `Script.py` |
| 36 | `get_readable_time` `0` par empty string | `utils.py:209` |
| 37 | `watch` sirf `video/*` support karta hai, audio nahi | `render_template.py:14-19` |
| 38 | `/download` par koi auth/token nahi — message id guess = file access | `stream_routes.py:25` |
| 39 | Koi global error handler / logging nahi (`on_error` missing) | `bot.py` |
| 40 | `requirements.txt` unpinned (sirf pyrofork pinned) | `requirements.txt` |

---

## 11. Duplication hotspots (= restructure ke asli targets)

| Pattern | Occurrences | Lines (approx) |
|---|---|---|
| **Group settings keyboard** (Auto Filter…Close) | `commands.py:275-309` **+** `pm_filter.py:734-768` | ~70 duplicate |
| **Search-result page builder** (files_link + btn + send_all + pagination + edit_text) | 6 handlers: `next_page`, `lang_search`, `lang_next`, `qual_search`, `qual_next`, `auto_filter` | ~370 (pm_filter ka 35%) |
| `files_link += …` snippet | **6** baar | |
| `NEXT ⏩` button block | **8** baar | |
| `Back To Main Page` | 5 baar | |
| **Group-admin boilerplate** (anonymous check + chat type + `is_check_admin`) | 7 commands (`set_template`, `set_caption`, `set_shortlink`, `get_custom_settings`, `set_welcome`, `set_tutorial`, `set_fsub`, `remove_fsub`) | ~60 |
| **Bot-admin guard** (`if user_id not in ADMINS: await message.delete(); return`) | 10+ | ~30 |
| `reply_photo(photo=random.choice(PICS))` | 3 | |
| **Premium plans UI** (QR + buttons + PREMIUM_PLAN_TEXT) | `start?plans`, `/plan`, `buy_premium` | ~30 |
| **File send + caption + delete timer** | `commands.py` all-files vs single file | ~60 |
| **`try: react except: react ⚡️`** | 12 handlers | ~36 |
| Caption format (`CAPTION.format(file_name, file_size, file_caption)`) | 4 | |

**Impact:** `pm_filter.py` (1073 lines) ko realistically **~450 lines** tak toda ja sakta hai; `commands.py` (694) → **~400**.

---

## 12. Suggested target structure (restructure plan)

```
bot.py                     # sirf entrypoint + run()
config.py                  # pydantic-settings, NO sys.exit(); required/optional split
core/
  client.py                # Bot(Client): startup/shutdown, health checks
  state.py                 # cache (TTLCache) — temp.* replace
  logger.py
db/
  client.py                # single AsyncIOMotorClient
  models/ media.py users.py chats.py settings.py premium.py
  repos/   media_repo.py users_repo.py chats_repo.py premium_repo.py
services/
  search_service.py        # get_search_results + pagination + lang/quality
  render_service.py        # build result text/keyboard (SIRF EK JAGAH)
  delivery_service.py      # send file/all + auto-delete + protect
  imdb_service.py          # async (thread pool) + cache
  shortlink_service.py
  verify_service.py
  premium_service.py
  settings_service.py      # default merge, cache invalidation
  telegram/
    session.py dc streaming
handlers/
  pm/ start.py verify.py premium.py search.py help.py
  group/ search.py settings.py admin_fsub.py manage.py moderation.py
  admin/ stats.py index.py broadcast.py users_chats.py system.py
  inline.py
ui/
  keyboards.py             # settings_kb(), result_kb(), nav_kb()
  texts.py                 # Script.py ki jagah (enum/keys)
web/
  app.py  routes/{root,watch,download}.py  templates/  static/  ← style.css serve
filters/
  admin.py group_admin.py banned.py fsub.py
tests/                     # pytest: regex builder, pagination, deep-link parser
```

**Mapping (purane → naye):**
`pm_filter.py` → `handlers/pm/search.py` + `handlers/group/search.py` + `services/render_service.py` + `services/delivery_service.py`
`commands.py` → `handlers/pm/start.py` + `handlers/pm/premium.py` + `handlers/group/settings.py` + `handlers/admin/*`
`p_ttishow.py` → `handlers/group/welcome.py` + `handlers/admin/{system,chat_admin,user_admin}.py`
`utils.py` → `services/*` + `core/state.py` + `filters/*`
`info.py` → `config.py` + `ui/texts.py`

---

## 13. Refactor roadmap (safe order)

| Phase | Kaam | Risk | Payoff |
|---|---|---|---|
| **P0 (1-2 din)** | §10 ke 10 P0 bugs fix; `/ping`, `/id`, `/ban`, `/start` crash, shared-dict bug, banned filter, mime fallback, style.css route | Bahut kam | Bot turant "kaam karta" lagne lagega |
| **P1** | `ui/keyboards.py` + `ui/texts.py` nikalo → duplicate settings keyboard & plans UI ek jagah | Kam | ~120 lines kam, ek jagah change |
| **P2** | `render_service` (single result builder) → 6 handlers → 2 generic handlers | Medium | ~350 lines kam, sab pages consistent |
| **P3** | `services/` layer: search, delivery, verify, premium, settings (shared-dict bug yahin fix) | Medium | Testable, business logic alag |
| **P4** | `config.py` pydantic + startup validation (sirf truly-required vars) | Kam | Deploy easy, `.env.example` |
| **P5** | DB layer: ek user collection, TTL cache, index ensure, repo methods | Medium-High | Data consistency, multi-instance safe |
| **P6** | Web: static route, proper mime, `/download` token, audio support | Kam | Streaming reliable |
| **P7** | Tests (pytest) + ruff + `.gitignore` + real README + CI | Kam | Regression safety |

**Quick wins (aaj hi, 1 ghante me):**
1. `pm_filter.py` se dead callbacks (`owner`, `earn`, `howshort`, `unmuteme`) hatao + `Script` ke 3 texts.
2. `commands.py` se commented `telegraph` block + imports.
3. `web/stream_routes.py` me `static` route add → `style.css` serve.
4. `badfiles` counter & duplicate `hindi/tamil` branch remove.
5. `.gitignore` (`__pycache__`, `*.txt` dumps) + `README.md` env table.
6. `SHORTLINK_API` default repo se hatado (env only).

---

## 14. Appendix A — handler inventory (57)

**Message (44):** `is_user_banned`, `is_group_disabled` · `users_broadcast`, `groups_broadcast` · `media` (channel) · `start`, `channels_info`, `stats`, `settings`, `save_template`, `save_caption`, `save_shortlink`, `get_custom_settings`, `save_welcome`, `delete_file`, `delete_all_index`, `set_tutorial`, `ping`, `give_premium_cmd_handler`, `remove_premium_cmd_handler`, `plans_list`, `check_plans_cmd`, `set_pm_search`, `set_fsub`, `remove_fsub` · `executor` · `members_management`, `ban_chat_user`, `mute_chat_user`, `unban_chat_user` · `send_for_index` · `showid`, `speedtest` · `restart_bot`, `leave_a_chat`, `disable_chat`, `re_enable_chat`, `gen_invite_link`, `ban_a_user`, `unban_a_user`, `list_users`, `list_chats` · `pm_search`, `group_search`

**Callback (11):** `broadcast_cancel` · `index_files` · `next_page`, `languages_`, `quality`, `filter_languages_cb_handler`, `lang_next_page`, `quality_search`, `quality_next_page`, `advantage_spoll_choker`, `cb_handler`

**Inline (1):** `inline_search` · **Member updated (1):** `welcome`

---

## 15. Appendix B — kaise verify kiya

```
python3 -m compileall .            → syntax clean (0 errors)
pyflakes $(git ls-files '*.py')    → 10 unused/duplicate warnings (§9 #16)
grep handlers / callback_data      → 57 handlers, 38 callbacks, 5 orphans
call-graph grep per function       → 6 dead functions (§9)
env var scan (info.py)             → 46 vars, 21 hard-exit
collection scan (db/*.py)          → 5 collections, 2 user collections
```

**Bottom line:** bot feature-rich hai (100+ chhote features), par `pm_filter.py` + `commands.py` me 55% code hai, ~450 lines duplicate, ~120 lines dead, 10 P0 bugs hain jo real users ko hit karte hain. Restructure ka sahi order: **bugs → UI extraction → result-render unification → services → config/DB → web → tests**.
