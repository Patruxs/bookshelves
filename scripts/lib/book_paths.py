from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable, Mapping
from pathlib import Path

from .constants import BOOK_EXTENSIONS, BOOKS_DIR, CATEGORY_PATTERN, COVER_EXTENSION

MIN_BOOK_PATH_PARTS = 3


def normalize_text(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def sanitize_filename(name: str) -> str:
    safe = re.sub(r"[^\w\s\-.]", "", normalize_text(name))
    safe = re.sub(r"\s+", "_", safe.strip())
    return safe[:100]


def cover_filename(title: str) -> str:
    return sanitize_filename(title) + COVER_EXTENSION


def detect_cover_collisions(books: Iterable[Mapping[str, object]]) -> dict[str, list[str]]:
    titles_by_cover: dict[str, set[str]] = {}
    for book in books:
        title = book.get("title")
        if not isinstance(title, str) or not title:
            continue
        titles_by_cover.setdefault(cover_filename(title), set()).add(normalize_text(title))
    return {
        cover: sorted(titles)
        for cover, titles in sorted(titles_by_cover.items())
        if len(titles) > 1
    }


def parse_category_name(folder_name: str) -> str:
    match = CATEGORY_PATTERN.match(folder_name)
    if match:
        return match.group(2).replace("_", " ")
    return folder_name.replace("_", " ")


def parse_topic_name(folder_name: str) -> str:
    return folder_name.replace("_", " ")


def display_to_folder_name(display_name: str) -> str:
    return display_name.replace(" ", "_")


def display_topic_from_parts(parts: tuple[str, ...]) -> str:
    return "/".join(parse_topic_name(part) for part in parts)


def generate_book_id(file_path: str) -> str:
    digest = hashlib.md5(normalize_text(file_path).encode("utf-8"), usedforsecurity=False)
    return digest.hexdigest()[:12]


def is_book_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in BOOK_EXTENSIONS


def metadata_from_book_path(base_dir: Path, file_path: Path) -> dict[str, object]:
    rel_path = file_path.relative_to(base_dir).as_posix()
    category, topic = expected_display_from_file_path(rel_path)
    if category is None or topic is None:
        raise ValueError(f"Unsupported book path: {rel_path}")

    return {
        "abs_path": file_path,
        "rel_path": rel_path,
        "filename": file_path.name,
        "title": file_path.stem,
        "category": category,
        "topic": topic,
        "format": file_path.suffix.lower()[1:],
        "size": file_path.stat().st_size,
    }


def expected_display_from_file_path(file_path: str) -> tuple[str | None, str | None]:
    parts = Path(file_path).parts
    if len(parts) < MIN_BOOK_PATH_PARTS or parts[0] != BOOKS_DIR:
        return None, None

    category = parse_category_name(parts[1])
    topic_parts = tuple(parts[2:-1])
    topic = display_topic_from_parts(topic_parts) if topic_parts else category
    return category, topic


BYTES_PER_KB = 1024
BYTES_PER_MB = BYTES_PER_KB * 1024
BYTES_PER_GB = BYTES_PER_MB * 1024


def format_size(size_bytes: int) -> str:
    if size_bytes < BYTES_PER_KB:
        return f"{size_bytes} B"
    if size_bytes >= BYTES_PER_GB:
        return f"{size_bytes / BYTES_PER_GB:.1f} GB"
    if size_bytes >= BYTES_PER_MB:
        return f"{size_bytes / BYTES_PER_MB:.1f} MB"
    return f"{size_bytes / BYTES_PER_KB:.0f} KB"
