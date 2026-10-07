from pathlib import Path

from conftest import (
    CORE_JAVA,
    DATABASE_INTERNALS,
    FIXTURE_BOOKS,
    FLUENT_PYTHON,
    CliResult,
    books_by_title,
    read_books,
    run_cli,
)

MOVED_FLUENT_PYTHON = "Books/1_Programming/Advanced_Python/Fluent_Python.pdf"


def ok_json(result: CliResult, command: str) -> dict:
    assert result.returncode == 0, f"{command} failed (exit {result.returncode}):\n{result.stderr}"
    payload = result.json()
    assert payload["ok"] is True, f"{command} --json reported failure: {payload}"
    return payload


def metadata_by_title(base_dir: Path) -> dict[str, tuple[str, str]]:
    return {
        title: (book.get("description", ""), book.get("download_url", ""))
        for title, book in books_by_title(base_dir).items()
    }


def fixture_metadata() -> dict[str, tuple[str, str]]:
    return {
        Path(file_path).stem: (extras.get("description", ""), extras.get("download_url", ""))
        for file_path, extras in FIXTURE_BOOKS.items()
    }


def set_topic(base_dir: Path, *mode: str) -> CliResult:
    return run_cli(
        "update", "--base-dir", base_dir, "--json", "--book", "Fluent_Python", "--set-topic", "Advanced Python", *mode
    )


def test_update_set_topic_dry_run_changes_nothing(fake_library: Path) -> None:
    before = (fake_library / "data" / "data.json").read_bytes()

    payload = ok_json(set_topic(fake_library), "update dry-run")

    assert payload["dry_run"] is True
    assert (fake_library / "data" / "data.json").read_bytes() == before
    assert (fake_library / FLUENT_PYTHON).is_file()


def test_update_execute_without_yes_needs_confirmation(fake_library: Path) -> None:
    before = (fake_library / "data" / "data.json").read_bytes()

    result = set_topic(fake_library, "--execute")

    assert result.returncode == 2, "execute without --yes and no TTY must exit 2 (confirmation required)"
    assert result.json()["ok"] is False
    assert (fake_library / "data" / "data.json").read_bytes() == before


def test_update_set_topic_moves_file_and_preserves_metadata(fake_library: Path) -> None:
    ok_json(set_topic(fake_library, "--execute", "--yes"), "update --set-topic")

    moved = books_by_title(fake_library)["Fluent_Python"]
    assert moved["file_path"] == MOVED_FLUENT_PYTHON
    assert moved["topic"] == "Advanced Python"
    assert (fake_library / MOVED_FLUENT_PYTHON).is_file()
    assert not (fake_library / FLUENT_PYTHON).exists()
    assert metadata_by_title(fake_library) == fixture_metadata()

    ok_json(run_cli("generate", "--base-dir", fake_library, "--json"), "generate after update")
    assert books_by_title(fake_library)["Fluent_Python"]["file_path"] == MOVED_FLUENT_PYTHON
    assert metadata_by_title(fake_library) == fixture_metadata()


def test_update_set_description(fake_library: Path) -> None:
    ok_json(
        run_cli(
            "update", "--base-dir", fake_library, "--json", "--book", "Core_Java",
            "--set-description", "Volume I", "--execute", "--yes",
        ),
        "update --set-description",
    )

    core_java = books_by_title(fake_library)["Core_Java"]
    assert core_java["description"] == "Volume I"
    assert core_java["download_url"] == FIXTURE_BOOKS[CORE_JAVA]["download_url"]


def test_delete_one_book_preserves_the_others(fake_library: Path) -> None:
    payload = ok_json(
        run_cli("delete", "--base-dir", fake_library, "--json", "--book", "Database_Internals", "--execute", "--yes"),
        "delete --book",
    )

    assert payload["dry_run"] is False
    remaining = fixture_metadata()
    del remaining["Database_Internals"]
    assert metadata_by_title(fake_library) == remaining
    assert (fake_library / DATABASE_INTERNALS).is_file(), "delete without --delete-files must keep the book file"

    ok_json(run_cli("generate", "--base-dir", fake_library, "--json"), "generate after delete")
    after_generate = metadata_by_title(fake_library)
    assert {title: after_generate[title] for title in remaining} == remaining


def test_delete_dry_run_changes_nothing(fake_library: Path) -> None:
    before = (fake_library / "data" / "data.json").read_bytes()

    payload = ok_json(
        run_cli("delete", "--base-dir", fake_library, "--json", "--category", "Databases"),
        "delete dry-run",
    )

    assert payload["dry_run"] is True
    assert (fake_library / "data" / "data.json").read_bytes() == before


def test_delete_partial_category_is_rejected(fake_library: Path) -> None:
    result = run_cli("delete", "--base-dir", fake_library, "--json", "--category", "Data", "--execute", "--yes")

    assert result.returncode != 0
    assert result.json()["ok"] is False
    assert "Did you mean" in result.json()["error"], "category selection must be exact and suggest names"
    assert len(read_books(fake_library)) == len(FIXTURE_BOOKS)


def test_delete_files_refuses_books_without_download_url(fake_library: Path) -> None:
    result = run_cli(
        "delete", "--base-dir", fake_library, "--json", "--book", "Database_Internals",
        "--delete-files", "--execute", "--yes",
    )

    assert result.returncode == 1
    assert result.json()["ok"] is False
    assert (fake_library / DATABASE_INTERNALS).is_file()
    assert len(read_books(fake_library)) == len(FIXTURE_BOOKS)


def test_delete_files_removes_file_and_empty_dirs(fake_library: Path) -> None:
    ok_json(
        run_cli(
            "delete", "--base-dir", fake_library, "--json", "--book", "Core_Java",
            "--delete-files", "--execute", "--yes",
        ),
        "delete --delete-files",
    )

    assert not (fake_library / CORE_JAVA).exists()
    assert not (fake_library / CORE_JAVA).parent.exists()
    assert "Core_Java" not in books_by_title(fake_library)
