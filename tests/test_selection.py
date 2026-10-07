import pytest

from lib.selection import SelectionError, match_key, resolve_selection, select_books

BOOKS = [
    {"id": "a1", "title": "Python", "category": "Programming", "topic": "Python"},
    {"id": "a2", "title": "Python_Cookbook", "category": "Programming", "topic": "Python"},
    {"id": "a3", "title": "Fluent_Python", "category": "Programming", "topic": "Python"},
    {"id": "b1", "title": "Core_Java", "category": "Programming Languages", "topic": "Java"},
    {"id": "c1", "title": "Head_First_Design_Patterns", "category": "Software Engineering", "topic": "Design/Patterns"},
    {"id": "c2", "title": "Refactoring", "category": "Software Engineering", "topic": "Design"},
]


def ids(books: list[dict]) -> list[str]:
    return [book["id"] for book in books]


def test_match_key_ignores_case_and_space_versus_underscore() -> None:
    assert match_key("Fluent Python") == match_key("fluent_python")


def test_exact_title_wins_over_partial() -> None:
    selection = resolve_selection(BOOKS, book="Python")

    assert ids(selection.books) == ["a1"]
    assert selection.exact


def test_exact_title_ignores_case_and_spaces() -> None:
    assert ids(select_books(BOOKS, book="fluent python")) == ["a3"]


def test_partial_title_raises_without_allow_partial() -> None:
    with pytest.raises(SelectionError, match="No book titled exactly"):
        select_books(BOOKS, book="Cookbook")


def test_unique_partial_title_with_allow_partial() -> None:
    selection = resolve_selection(BOOKS, book="Cookbook", allow_partial=True)

    assert ids(selection.books) == ["a2"]
    assert not selection.exact


def test_ambiguous_partial_title_requires_all_matches() -> None:
    with pytest.raises(SelectionError, match="ambiguous"):
        select_books(BOOKS, book="Pyth", allow_partial=True)

    selected = select_books(BOOKS, book="Pyth", allow_partial=True, all_matches=True)
    assert sorted(ids(selected)) == ["a1", "a2", "a3"]


def test_unknown_title_suggests_names() -> None:
    with pytest.raises(SelectionError, match="Did you mean"):
        select_books(BOOKS, book="Refactorng")


def test_exact_category_does_not_include_longer_names() -> None:
    assert sorted(ids(select_books(BOOKS, category="Programming"))) == ["a1", "a2", "a3"]


def test_partial_category_raises_with_suggestion() -> None:
    with pytest.raises(SelectionError, match="Did you mean"):
        select_books(BOOKS, category="Prog")


@pytest.mark.parametrize("flag", [{"allow_partial": True}, {"all_matches": True}])
def test_partial_category_raises_even_with_partial_flags(flag: dict[str, bool]) -> None:
    with pytest.raises(SelectionError):
        select_books(BOOKS, category="Prog", **flag)


def test_exact_topic_does_not_include_subtopics() -> None:
    assert ids(select_books(BOOKS, topic="Design", category="Software Engineering")) == ["c2"]
    assert ids(select_books(BOOKS, topic="design/patterns", category="software engineering")) == ["c1"]


def test_partial_topic_raises() -> None:
    with pytest.raises(SelectionError, match="Did you mean"):
        select_books(BOOKS, topic="Patterns", category="Software Engineering")


def test_topic_requires_category() -> None:
    with pytest.raises(SelectionError, match="requires --category"):
        select_books(BOOKS, topic="Python")


def test_book_id_selection_and_duplicates() -> None:
    assert ids(select_books(BOOKS, book_id="b1")) == ["b1"]
    with pytest.raises(SelectionError, match="more than one"):
        select_books([*BOOKS, {"id": "b1", "title": "Copy"}], book_id="b1")
    with pytest.raises(SelectionError):
        select_books(BOOKS, book_id="zz")


def test_no_selector_raises() -> None:
    with pytest.raises(SelectionError, match="No selection"):
        select_books(BOOKS)
