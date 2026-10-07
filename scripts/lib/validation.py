from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlparse

from .book_paths import expected_display_from_file_path
from .constants import (
    BOOK_EXTENSIONS,
    COVER_DIR,
    COVER_EXTENSION,
    COVER_SIZE_WARNING_BYTES,
    DATA_JSON,
)
from .covers import dependency_status
from .json_io import load_books

REQUIRED_FIELDS = {
    "id",
    "title",
    "category",
    "topic",
    "file_path",
    "cover",
    "format",
    "description",
}


@dataclass
class ValidationIssue:
    severity: str
    code: str
    message: str
    file: str = DATA_JSON

    def as_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "file": self.file,
        }


def validate_library(base_dir: Path, *, include_dependencies: bool = True) -> dict[str, Any]:
    base_dir = base_dir.resolve()
    issues: list[ValidationIssue] = []
    environment = _environment_warnings() if include_dependencies else []

    data_path = base_dir / DATA_JSON
    if not data_path.exists():
        issues.append(ValidationIssue("error", "missing_data_json", f"{DATA_JSON} is missing"))
        return _result([], issues, base_dir, environment)

    try:
        books = load_books(base_dir)
    except (OSError, ValueError) as exc:
        issues.append(ValidationIssue("error", "invalid_json", f"Cannot read {DATA_JSON}: {exc}"))
        return _result([], issues, base_dir, environment)

    _validate_entries(base_dir, books, issues)
    return _result(books, issues, base_dir, environment)


def _environment_warnings() -> list[str]:
    return [
        f"{name} is not installed; cover extraction that needs it is unavailable"
        for name, available in dependency_status().items()
        if not available
    ]


def _validate_entries(base_dir: Path, books: list[Any], issues: list[ValidationIssue]) -> None:
    seen_ids: dict[str, int] = {}
    seen_paths: dict[str, int] = {}

    for index, book in enumerate(books):
        location = f"{DATA_JSON} entry {index}"
        if not isinstance(book, dict):
            issues.append(
                ValidationIssue(
                    "error", "invalid_entry", f"Entry must be an object, got {type(book).__name__}", location
                )
            )
            continue

        missing = sorted(REQUIRED_FIELDS - set(book.keys()))
        if missing:
            issues.append(
                ValidationIssue("error", "missing_fields", f"Missing fields {missing}", location)
            )

        book_id = book.get("id")
        if not isinstance(book_id, str) or not book_id:
            issues.append(
                ValidationIssue("error", "empty_id", f"Book id is empty or not a string: {book_id!r}", location)
            )
        else:
            if book_id in seen_ids:
                issues.append(
                    ValidationIssue("error", "duplicate_id", f"Duplicate id {book_id}", location)
                )
            seen_ids[book_id] = index

        file_path = book.get("file_path")
        if not isinstance(file_path, str) or not file_path:
            issues.append(ValidationIssue("error", "empty_file_path", "file_path is empty", location))
            continue
        if file_path in seen_paths:
            issues.append(
                ValidationIssue("error", "duplicate_file_path", f"Duplicate file_path {file_path}", location)
            )
        seen_paths[file_path] = index

        _validate_path_metadata(base_dir, book, file_path, location, issues)
        _validate_download_url(book, file_path, location, issues)
        _validate_cover(base_dir, book, location, issues)


def _validate_path_metadata(
    base_dir: Path,
    book: dict[str, Any],
    file_path: str,
    location: str,
    issues: list[ValidationIssue],
) -> None:
    expected_category, expected_topic = expected_display_from_file_path(file_path)
    if expected_category is None or expected_topic is None:
        issues.append(ValidationIssue("error", "invalid_file_path", f"Invalid book path {file_path}", location))
        return

    suffix = Path(file_path).suffix.lower()
    if suffix not in BOOK_EXTENSIONS:
        issues.append(ValidationIssue("error", "unsupported_format", f"Unsupported file format {suffix}", location))

    if book.get("category") != expected_category:
        issues.append(
            ValidationIssue(
                "error",
                "category_mismatch",
                f"category should be {expected_category!r} for {file_path}",
                location,
            )
        )
    if book.get("topic") != expected_topic:
        issues.append(
            ValidationIssue(
                "error",
                "topic_mismatch",
                f"topic should be {expected_topic!r} for {file_path}",
                location,
            )
        )

    expected_format = suffix.lstrip(".")
    if book.get("format") != expected_format:
        issues.append(
            ValidationIssue("error", "format_mismatch", f"format should be {expected_format!r}", location)
        )

    local_file = base_dir / file_path
    if not local_file.exists() and not book.get("download_url"):
        issues.append(
            ValidationIssue(
                "error",
                "missing_file_and_url",
                f"{file_path} is absent locally and has no download_url",
                location,
            )
        )


def download_url_filename(download_url: str) -> str:
    return unquote(PurePosixPath(urlparse(download_url).path).name)


def _validate_download_url(book: dict[str, Any], file_path: str, location: str, issues: list[ValidationIssue]) -> None:
    download_url = book.get("download_url")
    if not isinstance(download_url, str) or not download_url:
        return
    asset_name = download_url_filename(download_url)
    expected_name = Path(file_path).name
    if asset_name != expected_name:
        issues.append(
            ValidationIssue(
                "warning",
                "download_url_mismatch",
                f"download_url points to {asset_name!r} but file_path is {expected_name!r}",
                location,
            )
        )


def _validate_cover(base_dir: Path, book: dict[str, Any], location: str, issues: list[ValidationIssue]) -> None:
    cover = book.get("cover")
    if cover is None or cover == "":
        issues.append(ValidationIssue("warning", "missing_cover", "cover is empty", location))
        return

    cover_prefix = f"{COVER_DIR}/"
    cover_name = cover[len(cover_prefix):] if isinstance(cover, str) and cover.startswith(cover_prefix) else ""
    if not cover_name or "/" in cover_name or not cover_name.endswith(COVER_EXTENSION):
        issues.append(ValidationIssue("error", "invalid_cover_path", f"Invalid cover path {cover}", location))
        return

    cover_path = base_dir / COVER_DIR / cover_name
    if not cover_path.exists():
        issues.append(ValidationIssue("error", "missing_cover_file", f"Cover file missing: {cover}", location))
        return
    size = cover_path.stat().st_size
    if size > COVER_SIZE_WARNING_BYTES:
        limit_kb = COVER_SIZE_WARNING_BYTES // 1024
        issues.append(
            ValidationIssue("warning", "large_cover", f"Cover exceeds {limit_kb}KB: {cover} ({size} bytes)", location)
        )


def _result(
    books: list[Any],
    issues: Iterable[ValidationIssue],
    base_dir: Path,
    environment: list[str],
) -> dict[str, Any]:
    issue_list = list(issues)
    errors = [issue.as_dict() for issue in issue_list if issue.severity == "error"]
    warnings = [issue.as_dict() for issue in issue_list if issue.severity == "warning"]
    missing_urls = sum(1 for book in books if isinstance(book, dict) and not book.get("download_url"))
    return {
        "ok": not errors,
        "summary": {
            "base_dir": base_dir.as_posix(),
            "books": len(books),
            "errors": len(errors),
            "warnings": len(warnings),
            "missing_download_urls": missing_urls,
        },
        "errors": errors,
        "warnings": warnings,
        "environment": environment,
    }
