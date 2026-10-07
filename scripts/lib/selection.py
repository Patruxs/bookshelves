from __future__ import annotations

import difflib
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .book_paths import normalize_text
from .json_io import Book


class SelectionError(ValueError):
    pass


MAX_SUGGESTIONS = 5
SIMILARITY_CUTOFF = 0.6
UNKNOWN = "Unknown"

NameOf = Callable[[Book], str]


@dataclass(frozen=True)
class Selection:
    books: list[Book]
    exact: bool
    matched_names: tuple[str, ...]

    @property
    def count(self) -> int:
        return len(self.books)

    @property
    def ambiguous(self) -> bool:
        return len(self.matched_names) > 1

    def report(self) -> dict[str, object]:
        return {"exact": self.exact, "matched_names": list(self.matched_names), "count": self.count}


def match_key(value: object) -> str:
    return normalize_text(str(value or "")).casefold().replace(" ", "_")


def title_of(book: Book) -> str:
    return str(book.get("title", ""))


def category_of(book: Book) -> str:
    return str(book.get("category", ""))


def topic_of(book: Book) -> str:
    return str(book.get("topic", ""))


def unique_names(books: list[Book], name_of: NameOf) -> tuple[str, ...]:
    return tuple(dict.fromkeys(name_of(book) for book in books))


def exact_matches(books: list[Book], name_of: NameOf, query: str) -> Selection:
    query_key = match_key(query)
    matches = [book for book in books if match_key(name_of(book)) == query_key]
    return Selection(matches, True, unique_names(matches, name_of))


def partial_matches(books: list[Book], name_of: NameOf, query: str) -> Selection:
    query_key = match_key(query)
    matches = [book for book in books if query_key and query_key in match_key(name_of(book))]
    return Selection(matches, False, unique_names(matches, name_of))


def suggest_names(books: list[Book], name_of: NameOf, query: str) -> list[str]:
    names = unique_names(books, name_of)
    names_by_key = {match_key(name): name for name in names}
    partial = list(partial_matches(books, name_of, query).matched_names)
    similar_keys = difflib.get_close_matches(match_key(query), list(names_by_key), n=MAX_SUGGESTIONS, cutoff=SIMILARITY_CUTOFF)
    similar = [names_by_key[key] for key in similar_keys]
    return list(dict.fromkeys([*partial, *similar]))[:MAX_SUGGESTIONS]


def did_you_mean(suggestions: list[str]) -> str:
    if not suggestions:
        return ""
    return " Did you mean: " + ", ".join(f'"{name}"' for name in suggestions) + "?"


def find_books_by_title(books: list[Book], title_query: str) -> Selection:
    exact = exact_matches(books, title_of, title_query)
    return exact if exact.books else partial_matches(books, title_of, title_query)


def find_books_by_id(books: list[Book], book_id: str) -> Selection:
    matches = [book for book in books if book.get("id") == book_id]
    return Selection(matches, True, (book_id,) if matches else ())


def find_books_by_category(books: list[Book], category: str) -> Selection:
    return exact_matches(books, category_of, category)


def find_books_by_topic(books: list[Book], topic: str, category: str) -> Selection:
    return exact_matches(find_books_by_category(books, category).books, topic_of, topic)


def duplicate_ids(books: list[Book]) -> set[str]:
    counts = Counter(str(book["id"]) for book in books if book.get("id"))
    return {book_id for book_id, count in counts.items() if count > 1}


def describe_book(book: Book) -> str:
    return f"{book.get('title', '?')} [{book.get('format', '?')}] (id: {book.get('id', '?')}) {book.get('file_path', '')}"


def list_candidates(books: list[Book]) -> str:
    return "\n".join(f"  - {describe_book(book)}" for book in books)


def require_category(books: list[Book], category: str) -> Selection:
    selection = find_books_by_category(books, category)
    if not selection.books:
        hint = did_you_mean(suggest_names(books, category_of, category))
        raise SelectionError(f'No category named "{category}".{hint} Use --list to see all categories.')
    return selection


def require_topic(books: list[Book], topic: str, category: str) -> Selection:
    in_category = require_category(books, category).books
    selection = exact_matches(in_category, topic_of, topic)
    if not selection.books:
        hint = did_you_mean(suggest_names(in_category, topic_of, topic))
        raise SelectionError(f'No topic named "{topic}" in category "{category}".{hint} Use --list to see all topics.')
    return selection


def require_title(books: list[Book], title: str, *, allow_partial: bool, all_matches: bool) -> Selection:
    exact = exact_matches(books, title_of, title)
    if exact.books:
        return exact
    partial = partial_matches(books, title_of, title)
    if not partial.books:
        hint = did_you_mean(suggest_names(books, title_of, title))
        raise SelectionError(f'No book titled "{title}".{hint} Use --list to see all available books.')
    if allow_partial and (not partial.ambiguous or all_matches):
        return partial
    if allow_partial:
        raise SelectionError(
            f'Title "{title}" is ambiguous: it partially matches {len(partial.matched_names)} different titles:\n'
            f"{list_candidates(partial.books)}\n"
            "Use the exact title, --book-id, or --all-matches."
        )
    raise SelectionError(
        f'No book titled exactly "{title}". Partial matches:\n'
        f"{list_candidates(partial.books)}\n"
        "Use the exact title, --book-id, or --fuzzy to accept a unique partial match."
    )


def require_book_id(books: list[Book], book_id: str) -> Selection:
    if book_id in duplicate_ids(books):
        raise SelectionError(f"Book id {book_id} is used by more than one entry; refusing to select by id.")
    selection = find_books_by_id(books, book_id)
    if not selection.books:
        raise SelectionError(f"No book with id {book_id}. Use --list to see all available books.")
    return selection


def resolve_selection(
    books: list[Book],
    *,
    book: str | None = None,
    book_id: str | None = None,
    topic: str | None = None,
    category: str | None = None,
    allow_partial: bool = False,
    all_matches: bool = False,
) -> Selection:
    if book_id:
        return require_book_id(books, book_id)
    if book:
        return require_title(books, book, allow_partial=allow_partial, all_matches=all_matches)
    if topic:
        if not category:
            raise SelectionError("--topic requires --category to disambiguate topics with the same name.")
        return require_topic(books, topic, category)
    if category:
        return require_category(books, category)
    raise SelectionError("No selection specified. Use --book, --book-id, --topic, or --category.")


def select_books(
    books: list[Book],
    *,
    book: str | None = None,
    book_id: str | None = None,
    topic: str | None = None,
    category: str | None = None,
    allow_partial: bool = False,
    all_matches: bool = False,
) -> list[Book]:
    return resolve_selection(
        books,
        book=book,
        book_id=book_id,
        topic=topic,
        category=category,
        allow_partial=allow_partial,
        all_matches=all_matches,
    ).books


def display_title(title: str) -> str:
    return title.replace("_", " ")


def categories_of(books: list[Book]) -> list[str]:
    return sorted({category_of(book) for book in books if book.get("category")})


def topics_of(books: list[Book], category: str | None = None) -> list[str]:
    return sorted({
        topic_of(book) for book in books
        if book.get("topic") and (category is None or book.get("category") == category)
    })


def group_books(books: list[Book]) -> dict[str, dict[str, list[Book]]]:
    tree: dict[str, dict[str, list[Book]]] = {}
    for book in books:
        tree.setdefault(book.get("category") or UNKNOWN, {}).setdefault(book.get("topic") or UNKNOWN, []).append(book)
    return {
        category: {
            topic: sorted(tree[category][topic], key=lambda book: display_title(title_of(book)).casefold())
            for topic in sorted(tree[category])
        }
        for category in sorted(tree)
    }


def build_library_tree(books: list[Book]) -> dict[str, dict[str, list[str]]]:
    tree: dict[str, dict[str, list[str]]] = {}
    for book in books:
        category = book.get("category", UNKNOWN)
        topic = book.get("topic", UNKNOWN)
        title = book.get("title", UNKNOWN)
        tree.setdefault(category, {}).setdefault(topic, []).append(title)
    return tree


def list_library(books: list[Book]) -> dict[str, object]:
    tree = build_library_tree(books)
    print(f"\n📚 Library Overview ({len(books)} books total)\n")
    print("=" * 60)
    for category in sorted(tree):
        category_count = sum(len(titles) for titles in tree[category].values())
        print(f"\n📂 {category} ({category_count} books)")
        for topic in sorted(tree[category]):
            titles = tree[category][topic]
            print(f"   📌 {topic} ({len(titles)} books)")
            for title in sorted(titles):
                print(f"      • {display_title(title)}")
    print(f"\n{'=' * 60}")
    return {"books": len(books), "tree": tree}


def remove_empty_parents(books_root: Path, files: list[Path]) -> list[Path]:
    resolved_root = books_root.resolve()
    removed: list[Path] = []
    parents = sorted({path.parent.resolve() for path in files}, key=lambda path: len(path.parts), reverse=True)
    for start in parents:
        directory = start
        while directory != resolved_root and directory.is_relative_to(resolved_root):
            if not directory.is_dir() or any(directory.iterdir()):
                break
            directory.rmdir()
            removed.append(directory)
            directory = directory.parent
    return removed

