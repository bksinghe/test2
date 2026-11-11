"""IMDb lookups.

Cinemagoer is a blocking library, so every call runs in a worker thread with a
timeout. The previous implementation called it directly inside async handlers,
which froze the whole event loop (and the bot) on slow responses.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from imdb import Cinemagoer

from config import settings
from core import state
from core.fmt import join_iterable

log = logging.getLogger(__name__)

TIMEOUT = 10
YEAR_RE = re.compile(r"[12]\d{3}")
_imdb = Cinemagoer()


def _year_of(query: str, file_name: str = "") -> str | None:
    match = YEAR_RE.search(query) or YEAR_RE.search(file_name)
    return match.group(0) if match else None


def _search_sync(title: str, year: str | None) -> list[Any]:
    results = list(_imdb.search_movie(title.lower()) or [])
    if year:
        filtered = [movie for movie in results if str(movie.get("year")) == year]
        results = filtered or results
    movies = [movie for movie in results if movie.get("kind") in ("movie", "tv series")]
    return movies or results


def _bulk_sync(query: str, file_name: str) -> list[dict[str, Any]]:
    title = query
    year = _year_of(query, file_name)
    if year:
        title = query.replace(year, "").strip() or query
    movies = _search_sync(title, year)
    return [
        {
            "id": str(movie.movieID),
            "title": movie.get("title") or title,
            "year": movie.get("year"),
            "kind": movie.get("kind"),
        }
        for movie in movies[:10]
    ]


def _details_sync(movie_id: str) -> dict[str, Any] | None:
    movie = _imdb.get_movie(movie_id)
    if not movie:
        return None

    date = movie.get("original air date") or movie.get("year") or "N/A"
    if settings.long_imdb:
        plot = movie.get("plot outline") or ""
    else:
        plots = movie.get("plot") or []
        plot = plots[0] if plots else ""
    if len(plot) > 800:
        plot = plot[:800] + "..."

    return {
        "title": movie.get("title"),
        "votes": movie.get("votes"),
        "aka": join_iterable(movie.get("akas")),
        "seasons": movie.get("number of seasons"),
        "box_office": movie.get("box office"),
        "localized_title": movie.get("localized title"),
        "kind": movie.get("kind"),
        "imdb_id": f"tt{movie.get('imdbID') or movie_id}",
        "cast": join_iterable(movie.get("cast")),
        "runtime": join_iterable(movie.get("runtimes")),
        "countries": join_iterable(movie.get("countries")),
        "certificates": join_iterable(movie.get("certificates")),
        "languages": join_iterable(movie.get("languages")),
        "director": join_iterable(movie.get("director")),
        "writer": join_iterable(movie.get("writer")),
        "producer": join_iterable(movie.get("producer")),
        "composer": join_iterable(movie.get("composer")),
        "cinematographer": join_iterable(movie.get("cinematographer")),
        "music_team": join_iterable(movie.get("music department")),
        "distributors": join_iterable(movie.get("distributors")),
        "release_date": date,
        "year": movie.get("year"),
        "genres": join_iterable(movie.get("genres")),
        "poster": movie.get("full-size cover url"),
        "plot": plot,
        "rating": str(movie.get("rating") or "N/A"),
        "url": f"https://www.imdb.com/title/tt{movie.get('imdbID') or movie_id}",
    }


async def _run(func, *args):
    return await asyncio.wait_for(asyncio.to_thread(func, *args), timeout=TIMEOUT)


async def details(query: str = "", *, movie_id: str | None = None, file_name: str = "") -> dict[str, Any] | None:
    """Full IMDb metadata. Returns ``None`` when nothing matches or on error."""
    cache_key = ("details", movie_id or query.lower(), file_name.lower())
    cached = state.imdb_cache.get(cache_key)
    if cached is not None:
        return cached or None

    try:
        if not movie_id:
            movies = await _run(_bulk_sync, query, file_name)
            if not movies:
                state.imdb_cache.set(cache_key, False)
                return None
            movie_id = movies[0]["id"]
        result = await _run(_details_sync, str(movie_id))
    except Exception as error:  # noqa: BLE001 - network/parsing/thread issues
        log.warning("imdb lookup failed for %r: %s", query or movie_id, error)
        return None

    state.imdb_cache.set(cache_key, result or False)
    return result


async def suggestions(query: str, file_name: str = "") -> list[dict[str, Any]]:
    cache_key = ("suggest", query.lower(), file_name.lower())
    cached = state.imdb_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        results = await _run(_bulk_sync, query, file_name)
    except Exception as error:  # noqa: BLE001
        log.warning("imdb suggestions failed for %r: %s", query, error)
        return []
    state.imdb_cache.set(cache_key, results)
    return results


async def title_for_id(movie_id: str) -> str | None:
    data = await details(movie_id=movie_id)
    return (data or {}).get("title")


__all__ = ["details", "suggestions", "title_for_id"]
