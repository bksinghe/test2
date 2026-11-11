"""Dependency free default templates.

Kept in their own module so :mod:`config` can import them without creating an
import cycle (``ui`` modules import ``config``).
"""

DEFAULT_IMDB_TEMPLATE = """<b>✅ Found: <code>{query}</code></b>

<b>🏷 Title:</b> <a href="{url}">{title}</a>
<b>🎭 Genres:</b> {genres}
<b>📆 Year:</b> <a href="{url}/releaseinfo">{year}</a>
<b>🌟 Rating:</b> <a href="{url}/ratings">{rating} / 10</a>
<b>☀️ Languages:</b> {languages}
<b>📀 Runtime:</b> {runtime}

<b>🗣 Requested by:</b> {mention}
<b>©️ Powered by:</b> {chat_title}"""

DEFAULT_FILE_CAPTION = """<b>📂 {file_name}</b>
<b>♻️ Size:</b> {file_size}"""

DEFAULT_WELCOME = "👋 Hello {mention}, welcome to {title}! 💞"

__all__ = ["DEFAULT_IMDB_TEMPLATE", "DEFAULT_FILE_CAPTION", "DEFAULT_WELCOME"]
