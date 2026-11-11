"""Boot order regression test.

Pyrogram calls ``asyncio.get_event_loop()`` while it is being imported, and
uvloop's policy raises instead of creating a loop on demand. Running the real
``bot.py`` boot sequence in a subprocess reproduces the deployment failure
("There is no current event loop in thread 'MainThread'") if the order ever
regresses.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

BOOT = """
import asyncio

import bot

loop = bot._make_loop()

import pyrogram  # noqa: F401  - this is the line that used to fail
from pyrogram import Client  # noqa: F401

print("OK", asyncio.get_event_loop() is loop)
"""


def test_event_loop_exists_before_pyrogram_import():
    result = subprocess.run(
        [sys.executable, "-c", BOOT],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    assert "OK True" in result.stdout
