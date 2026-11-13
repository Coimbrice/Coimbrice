from datetime import date

from stats import render_languages, top_languages


def contribution(repo, language, commits, color="#123456"):
    primary = {"name": language, "color": color} if language else None
    return {
        "name": repo,
        "primaryLanguage": primary,
        "defaultBranchRef": {"target": {"history": {"totalCount": commits}}},
    }


def test_commits_are_summed_per_language():
    contributions = [
        contribution("a", "C", 30),
        contribution("b", "C", 10),
        contribution("c", "Kotlin", 10),
    ]
    assert top_languages(contributions) == [("C", "#123456", 80.0), ("Kotlin", "#123456", 20.0)]


def test_markup_ignored_repos_and_repos_without_language_are_skipped():
    contributions = [
        contribution("site", "HTML", 100),
        contribution("dotfiles", "Lua", 100),
        contribution("notes", None, 100),
        contribution("game", "C", 1),
    ]
    assert top_languages(contributions) == [("C", "#123456", 100.0)]


def test_no_commits_is_empty():
    empty = {
        "name": "new",
        "primaryLanguage": {"name": "C", "color": None},
        "defaultBranchRef": None,
    }
    assert top_languages([empty, contribution("old", "C", 0)]) == []


def test_only_the_top_languages_are_kept():
    contributions = [contribution(str(i), f"Lang{i}", 10 - i) for i in range(8)]
    assert len(top_languages(contributions)) == 5


def test_card_lists_languages_and_date():
    svg = render_languages([("C", "#555555", 75.0), ("<T>", "#3178c6", 25.0)], date(2026, 11, 13))
    assert "75%" in svg
    assert "&lt;T&gt;" in svg
    assert "<T>" not in svg
    assert "updated 2026-11-13" in svg


def test_card_without_languages_still_renders():
    svg = render_languages([], date(2026, 11, 13))
    assert svg.startswith("<svg")
    assert "stroke-dasharray" not in svg
