from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lib.constants import INBOX_DIR
from lib.json_io import Book, load_books
from lib.selection import group_books

LibraryTree = dict[str, dict[str, list[Book]]]


@dataclass(frozen=True)
class LibraryStats:
    books: int
    categories: int
    topics: int
    inbox_files: int


def list_inbox_files(base_dir: Path) -> list[Path]:
    inbox = base_dir / INBOX_DIR
    if not inbox.is_dir():
        return []
    return sorted(
        path for path in inbox.rglob("*")
        if path.is_file() and not any(part.startswith(".") for part in path.relative_to(inbox).parts)
    )


def read_stats(base_dir: Path) -> LibraryStats:
    try:
        books = load_books(base_dir)
    except (OSError, ValueError):
        books = []
    tree = group_books(books)
    return LibraryStats(
        books=len(books),
        categories=len(tree),
        topics=sum(len(topics) for topics in tree.values()),
        inbox_files=len(list_inbox_files(base_dir)),
    )
