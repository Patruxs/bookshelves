import shutil
from pathlib import Path

from conftest import (
    CORE_JAVA,
    DATABASE_INTERNALS,
    EFFECTIVE_PYTHON,
    FIXTURE_BOOKS,
    FLUENT_PYTHON,
    books_by_title,
    read_books,
    run_cli,
)
from lib.constants import COVER_DIR


def preserved_fields(base_dir: Path) -> dict[str, tuple[str, str]]:
    return {
        book["file_path"]: (book.get("description", ""), book.get("download_url", ""))
        for book in read_books(base_dir)
    }


def expected_fields() -> dict[str, tuple[str, str]]:
    return {
        file_path: (extras.get("description", ""), extras.get("download_url", ""))
        for file_path, extras in FIXTURE_BOOKS.items()
    }


def generate(base_dir: Path, *extra: str) -> dict:
    result = run_cli("generate", "--base-dir", base_dir, "--json", *extra)
    assert result.returncode == 0, f"generate failed:\n{result.stderr}"
    summary = result.json()
    assert summary["ok"] is True, "generate --json must print only the JSON summary on stdout"
    return summary


def test_generate_twice_preserves_description_and_download_url(fake_library: Path) -> None:
    first = generate(fake_library)
    assert first["books_written"] == len(FIXTURE_BOOKS)
    assert preserved_fields(fake_library) == expected_fields()

    generate(fake_library)
    assert preserved_fields(fake_library) == expected_fields()


def test_generate_extracts_missing_covers_from_pdfs(fake_library: Path) -> None:
    shutil.rmtree(fake_library / COVER_DIR)

    summary = generate(fake_library)

    assert summary["covers"]["extracted"] == len(FIXTURE_BOOKS)
    assert summary["covers"]["failed"] == 0
    for book in read_books(fake_library):
        assert (fake_library / book["cover"]).is_file()


def test_generate_dry_run_writes_nothing(fake_library: Path) -> None:
    before = (fake_library / "data" / "data.json").read_bytes()
    (fake_library / "Books/1_Programming/Python/New_Book.pdf").write_bytes(
        (fake_library / FLUENT_PYTHON).read_bytes()
    )

    summary = generate(fake_library, "--dry-run")

    assert summary["dry_run"] is True
    assert summary["books_scanned"] == len(FIXTURE_BOOKS) + 1
    assert (fake_library / "data" / "data.json").read_bytes() == before


def test_generate_adds_new_book_with_empty_metadata(fake_library: Path) -> None:
    shutil.copy(fake_library / FLUENT_PYTHON, fake_library / "Books/1_Programming/Java/Effective_Java.pdf")

    generate(fake_library)

    books = books_by_title(fake_library)
    assert books["Effective_Java"]["topic"] == "Java"
    assert books["Effective_Java"]["description"] == ""
    assert "download_url" not in books["Effective_Java"]
    assert preserved_fields(fake_library) == {
        **expected_fields(),
        "Books/1_Programming/Java/Effective_Java.pdf": ("", ""),
    }


def test_generate_carries_metadata_when_file_moves(fake_library: Path) -> None:
    target = fake_library / "Books/1_Programming/Advanced_Python/Fluent_Python.pdf"
    target.parent.mkdir()
    (fake_library / FLUENT_PYTHON).rename(target)

    summary = generate(fake_library)

    assert summary["moved"] == [{"from": FLUENT_PYTHON, "to": "Books/1_Programming/Advanced_Python/Fluent_Python.pdf"}]
    moved = books_by_title(fake_library)["Fluent_Python"]
    assert moved["topic"] == "Advanced Python"
    assert moved["description"] == FIXTURE_BOOKS[FLUENT_PYTHON]["description"]
    assert moved["download_url"] == FIXTURE_BOOKS[FLUENT_PYTHON]["download_url"]


def test_generate_keeps_missing_file_with_download_url_and_drops_without(fake_library: Path) -> None:
    (fake_library / CORE_JAVA).unlink()
    (fake_library / DATABASE_INTERNALS).unlink()

    summary = generate(fake_library)

    assert summary["stale_kept"] == 1
    assert summary["stale_removed"] == 1
    paths = {book["file_path"] for book in read_books(fake_library)}
    assert CORE_JAVA in paths
    assert DATABASE_INTERNALS not in paths
    assert EFFECTIVE_PYTHON in paths


def test_generate_refuses_to_wipe_data_when_books_dir_is_empty(fake_library: Path) -> None:
    shutil.rmtree(fake_library / "Books")
    before = (fake_library / "data" / "data.json").read_bytes()

    result = run_cli("generate", "--base-dir", fake_library, "--json")

    assert result.returncode == 1
    assert result.json()["ok"] is False
    assert (fake_library / "data" / "data.json").read_bytes() == before
