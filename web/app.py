"""aiohttp application factory."""

from __future__ import annotations

from pathlib import Path

from aiohttp import web

from web.routes import routes

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)
    # the old bot shipped style.css but never served it (404 on every player page)
    if STATIC_DIR.is_dir():
        app.router.add_static("/static/", path=str(STATIC_DIR), name="static")
    return app


__all__ = ["STATIC_DIR", "create_app"]
