# Auto Filter Bot

Telegram bot that indexes media from channels and serves it as an inline
search + auto filter bot, with streaming, deep links, verification, force
subscribe and a small premium system.

This is a full rewrite of the original `Auto-Filter-Bot` fork: same features and
same database collection names, but the 4k-line pile of `plugins/` modules was
split into layers (`ui`, `core`, `db`, `services`, `handlers`, `web`). The audit
of the old code (bugs found, dead code removed, duplication measured) lives in
[`docs/AUDIT.md`](docs/AUDIT.md).

---

## Features

* **Indexing** – forward a post or send a `t.me` link, then `yes/no` for
  pagination; auto indexing of `INDEX_CHANNELS` on startup; skip prompt and
  cancel button; progress with saved / duplicate / deleted / skipped counts.
* **Search** – single query pipeline shared by PM search, group auto filter and
  the "did you mean" flow; regex search with word boundaries, optional caption
  search, language / quality filters, pagination and `send all`.
* **Delivery** – files sent from the bin channel with per-group caption
  templates, `protect_content`, auto delete timer and a "get files again"
  button.
* **Streaming** – `/watch/<id>` page plus `/download/<id>` with HTTP range
  support, HMAC signed links (`STREAM_SECRET`) and a cached bin-channel message
  so a file is uploaded to the bin channel only once.
* **Access control** – force subscribe, token verification gate, banned users,
  disabled chats, group admin / bot admin guards.
* **Per group settings** – 9 toggles + templates, shortlink, tutorial, url/api
  and force-subscribe channel list, cached with invalidation.
* **Premium** – plan page, manual add/remove, free trial (once per user),
  shortlink bypass for premium users.
* **Admin** – stats, broadcast (users + groups), leave/ban/unban chats,
  ban/unban users, list users/chats, index channels, delete files, restart,
  speedtest, eval, pin broadcast, PM search toggle.
* **Web** – aiohttp app used both for the player page and the range based
  download endpoint, static assets served from `web/static`.

## Layout

```
bot.py                  entry point: settings validation, plugins, web server
config.py               env driven settings (no side effects on import)
ui/                     texts, keyboards and default templates
core/                   cache, shared state, clock, formatting, logging, client
db/                     motor repositories (media, users, chats, meta)
services/               everything with behaviour and no telegram handlers
handlers/               thin telegram handlers, grouped by audience
web/                    aiohttp routes, template rendering, range streaming
scripts/migrate_db.py   legacy -> new schema migration
tests/                  pytest suite (no network, no database)
```

Dependency direction is one way: `handlers → services → db/core → config → ui`.
Handlers never touch motor directly and services never build keyboards.

### Handler groups

Pyrogram 2 dispatches only the **first matching handler per group**, so the
groups are meaningful:

| group | what runs | why |
|-------|-----------|-----|
| `-10` | banned user / disabled chat guards | can `StopPropagation` before anything answers |
| `0`   | commands, menus, admin actions | one handler per callback prefix |
| `10`  | PM search, group auto filter | runs only if no command matched |

### Callback data

`menu#<name>`, `settings#<key>#<chat_id>`, `nav#<key>#<viewer>#<offset>`,
`navf#<type>#<value>#<key>#<viewer>#<offset>`, `filtermenu#<type>#<key>#<viewer>#<offset>`,
`filter#<type>#<value>#<key>#<viewer>#<offset>`, `sendall#<key>#<viewer>`,
`file#<file_id>`, `regain#<type>#<chat_id>#<token>`, `stream#<file_id>`,
`checksub#<payload>`, `index#<action>`, `broadcast_cancel#<token>`,
`mgmt#<action>`, `suggest#<imdb_id>#<viewer>`, `close`, `noop`.

## Commands

**Everyone (PM):** `/start`, `/plan`, `/myplan`, `/id`, `/ping`

**Group admins:** `/settings`, `/set_template`, `/set_caption`, `/set_shortlink`,
`/get_custom_settings`, `/set_welcome`, `/set_tutorial`, `/set_fsub`,
`/remove_fsub`, `/manage`, `/ban`, `/mute`, `/unban`, `/unmute`

**Bot admins:** `/stats`, `/index_channels`, `/delete`, `/delete_all`,
`/add_premium`, `/remove_premium`, `/set_pm_search`, `/broadcast`,
`/pin_broadcast`, `/grp_broadcast`, `/pin_grp_broadcast`, `/restart`, `/leave`,
`/ban_grp`, `/unban_grp`, `/invite_link`, `/ban_user`, `/unban_user`, `/users`,
`/chats`, `/speedtest`, `/eval`

## Configuration

Every knob is documented in [`.env.example`](.env.example). Mandatory:
`API_ID`, `API_HASH`, `BOT_TOKEN`, `ADMINS`, `LOG_CHANNEL`, `DATABASE_URL`.
`URL` and `BIN_CHANNEL` are required when `IS_STREAM=true`.

Missing values are collected and printed once on startup by
`Settings.validate()` – importing `config` never kills the process, which is why
the test suite can import the package without a real environment.

## Running

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit it
python bot.py
```

Docker:

```bash
docker build -t auto-filter-bot .
docker run --env-file .env -p 80:80 auto-filter-bot
```

## Migrating an existing deployment

The new code reads the same `Files` collection, so indexed media keeps working.
Bans, verification, premium, group settings and the PM search flag changed
shape; convert them once with:

```bash
python scripts/migrate_db.py           # dry run
python scripts/migrate_db.py --apply   # write
```

The legacy collections (`uersz`, `bot_id`) are only read, never modified, so
rollback is just deploying the old image again.

## Development

```bash
pip install -r requirements-dev.txt
ruff check .        # lint
python -m pytest    # 60 unit tests, no network / no database
```

The tests cover deep-link parsing, the search filter builder, the cache /
clock / formatting helpers and the HTTP range logic.
