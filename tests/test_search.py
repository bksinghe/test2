"""Query building for the media index."""

from __future__ import annotations

import re

from services import search


def test_single_word_uses_boundaries():
    pattern = search.compile_query("avengers")
    assert pattern.search("The Avengers 2012 1080p")
    assert pattern.search("Avengers.Endgame.mkv")
    assert not pattern.search("avengerssss")


def test_multi_word_allows_separators():
    pattern = search.compile_query("avengers endgame")
    assert pattern.search("Avengers.Endgame.2019.1080p")
    assert pattern.search("avengers_endgame_2019")
    assert pattern.search("Avengers Endgame")
    assert not pattern.search("avengers")


def test_empty_query_matches_everything():
    pattern = search.compile_query("   ")
    assert pattern.search("anything")


def test_caption_filter_is_applied():
    filt = search.build_filter("movie", caption_filter=True)
    assert "$or" in filt
    names = {key for clause in filt["$or"] for key in clause}
    assert names == {"file_name", "caption"}


def test_caption_filter_can_be_disabled():
    filt = search.build_filter("movie", caption_filter=False)
    assert set(filt) == {"file_name"}


def test_language_and_quality_are_combined_with_and():
    filt = search.build_filter("movie", lang="hindi", quality="1080p", caption_filter=False)
    assert "$and" in filt
    assert len(filt["$and"]) == 3
    for clause in filt["$and"]:
        assert isinstance(clause["file_name"], re.Pattern)


def test_special_characters_are_escaped():
    pattern = search.compile_query("a+b")
    assert pattern.search("xx a+b yy") is not None
    # "+" must be a literal, not a regex quantifier
    assert pattern.search("aab") is None


def test_delete_filter_only_uses_file_name():
    _, filt = None, search.build_filter("x", caption_filter=False)
    assert "file_name" in filt
