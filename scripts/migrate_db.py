#!/usr/bin/env python3
"""Migrate an existing (legacy) database to the schema this bot expects.

The bot migrates itself on startup, so this script is only needed to *see* what
would change, or to repair a database before deploying. Both modes use the
same code as the startup path (:mod:`db.migrate`), so nothing here can drift
away from the runtime behaviour.

Usage::

    python scripts/migrate_db.py            # report only, writes nothing
    python scripts/migrate_db.py --apply    # convert, merge duplicates, build indexes

Nothing is deleted: legacy fields are replaced in place, legacy collections
(``uersz``, ``bot_id``) are only read, and merged duplicates keep the union of
their data (a ban or a premium flag is never lost).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings  # noqa: E402
from db import migrate, mongo  # noqa: E402


async def report() -> None:
    counts = await migrate.pending_counts()
    print(f"database: {settings.database_name}")
    print(f"users needing migration:   {counts['users']}")
    print(f"groups needing migration:  {counts['groups']}")
    print(f"premium rows in 'uersz':   {counts['premium']}")
    print(f"duplicate rows (users+chats): {counts['duplicates']}")
    print("\nnothing was written - rerun with --apply")


async def apply() -> None:
    print(f"database: {settings.database_name}")
    touched = await migrate.run()
    for step, count in touched.items():
        print(f"{step}: {count} document(s) migrated")
    await mongo.ensure_indexes()
    print("duplicates merged and indexes checked")


async def main(should_apply: bool) -> int:
    if not await mongo.ping():
        print("cannot reach MongoDB - check DATABASE_URL", file=sys.stderr)
        return 1
    try:
        if should_apply:
            await apply()
        else:
            await report()
    finally:
        await mongo.close()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the changes")
    raise SystemExit(asyncio.run(main(parser.parse_args().apply)))
