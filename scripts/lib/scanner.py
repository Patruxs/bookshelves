from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .book_paths import is_book_file, metadata_from_book_path
from .constants import BOOKS_DIR, CATEGORY_PATTERN, EXTENSION_PRIORITY


@dataclass(frozen=True)
class SkippedFile:
    path: str
    reason: str


@dataclass
class ScanResult:
    books: list[dict[str, object]] = field(default_factory=list)
    skipped: list[SkippedFile] = field(default_factory=list)


def scan_library(base_dir: Path) -> ScanResult:
    result = ScanResult()
    books_root = base_dir / BOOKS_DIR
    if not books_root.is_dir():
        return result

    for cat_folder in sorted(books_root.iterdir()):
        if not cat_folder.is_dir() or not CATEGORY_PATTERN.match(cat_folder.name):
            continue

        for root, dirs, files in os.walk(cat_folder):
            dirs.sort()
            root_path = Path(root)
            for filename in sorted(files, key=_book_sort_key):
                file_path = root_path / filename
                if not is_book_file(file_path):
                    continue
                try:
                    result.books.append(metadata_from_book_path(base_dir, file_path))
                except (OSError, ValueError) as exc:
                    rel_path = file_path.relative_to(base_dir).as_posix()
                    result.skipped.append(SkippedFile(rel_path, str(exc)))
    return result


def scan_book_files(base_dir: Path) -> list[dict[str, object]]:
    return scan_library(base_dir).books


def _book_sort_key(name: str) -> tuple[str, int, str]:
    path = Path(name)
    return path.stem, EXTENSION_PRIORITY.get(path.suffix.lower(), len(EXTENSION_PRIORITY)), name
