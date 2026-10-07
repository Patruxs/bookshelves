import json
from pathlib import Path

from conftest import read_books
from lib.constants import COVER_DIR, COVER_SIZE_WARNING_BYTES, DATA_JSON
from lib.validation import validate_library


def write_books(base_dir: Path, books: list[dict]) -> None:
    (base_dir / DATA_JSON).write_text(json.dumps(books), encoding="utf-8")


def codes(issues: list[dict]) -> list[str]:
    return [issue["code"] for issue in issues]


def test_fixture_library_is_clean(fake_library: Path) -> None:
    result = validate_library(fake_library, include_dependencies=False)

    assert result["ok"], result["errors"]
    assert result["errors"] == []
    assert result["warnings"] == []
    assert result["summary"]["books"] == 5
    assert result["summary"]["missing_download_urls"] == 3


def test_detects_topic_mismatch(fake_library: Path) -> None:
    books = read_books(fake_library)
    books[0]["topic"] = "Wrong Topic"
    write_books(fake_library, books)

    result = validate_library(fake_library, include_dependencies=False)

    assert not result["ok"]
    assert codes(result["errors"]) == ["topic_mismatch"]


def test_detects_category_mismatch(fake_library: Path) -> None:
    books = read_books(fake_library)
    books[0]["category"] = "Wrong"
    write_books(fake_library, books)

    assert "category_mismatch" in codes(validate_library(fake_library, include_dependencies=False)["errors"])


def test_warns_on_empty_cover(fake_library: Path) -> None:
    books = read_books(fake_library)
    books[0]["cover"] = ""
    write_books(fake_library, books)

    result = validate_library(fake_library, include_dependencies=False)

    assert result["ok"]
    assert codes(result["warnings"]) == ["missing_cover"]


def test_detects_missing_cover_file(fake_library: Path) -> None:
    books = read_books(fake_library)
    (fake_library / books[0]["cover"]).unlink()

    result = validate_library(fake_library, include_dependencies=False)

    assert codes(result["errors"]) == ["missing_cover_file"]


def test_warns_on_large_cover(fake_library: Path) -> None:
    books = read_books(fake_library)
    cover_path = fake_library / COVER_DIR / Path(books[0]["cover"]).name
    cover_path.write_bytes(b"\0" * (COVER_SIZE_WARNING_BYTES + 1))

    result = validate_library(fake_library, include_dependencies=False)

    assert result["ok"]
    assert codes(result["warnings"]) == ["large_cover"]


def test_detects_missing_file_without_download_url(fake_library: Path) -> None:
    books = read_books(fake_library)
    without_url = next(book for book in books if not book.get("download_url"))
    with_url = next(book for book in books if book.get("download_url"))
    (fake_library / without_url["file_path"]).unlink()
    (fake_library / with_url["file_path"]).unlink()

    result = validate_library(fake_library, include_dependencies=False)

    assert codes(result["errors"]) == ["missing_file_and_url"]


def test_detects_duplicate_id(fake_library: Path) -> None:
    books = read_books(fake_library)
    books[1]["id"] = books[0]["id"]
    write_books(fake_library, books)

    assert "duplicate_id" in codes(validate_library(fake_library, include_dependencies=False)["errors"])


def test_reports_missing_and_invalid_data_json(tmp_path: Path) -> None:
    assert codes(validate_library(tmp_path, include_dependencies=False)["errors"]) == ["missing_data_json"]

    (tmp_path / "data").mkdir()
    (tmp_path / DATA_JSON).write_text("{}", encoding="utf-8")
    assert codes(validate_library(tmp_path, include_dependencies=False)["errors"]) == ["invalid_json"]
