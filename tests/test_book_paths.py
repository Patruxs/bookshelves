import pytest

from lib.book_paths import (
    cover_filename,
    detect_cover_collisions,
    display_to_folder_name,
    expected_display_from_file_path,
    format_size,
    generate_book_id,
    parse_category_name,
    parse_topic_name,
    sanitize_filename,
)


@pytest.mark.parametrize(
    ("folder_name", "display_name"),
    [
        ("1_Programming", "Programming"),
        ("12_Software_Engineering", "Software Engineering"),
        ("No_Number", "No Number"),
    ],
)
def test_parse_category_name(folder_name: str, display_name: str) -> None:
    assert parse_category_name(folder_name) == display_name


def test_parse_topic_name_and_back() -> None:
    assert parse_topic_name("Programming_Languages") == "Programming Languages"
    assert display_to_folder_name("Programming Languages") == "Programming_Languages"


@pytest.mark.parametrize(
    ("file_path", "expected"),
    [
        ("Books/1_Programming/Python/Fluent_Python.pdf", ("Programming", "Python")),
        (
            "Books/4_Computer_Science/Programming_Languages/Java/Core_Java.pdf",
            ("Computer Science", "Programming Languages/Java"),
        ),
        ("Books/2_Databases/Database_Internals.pdf", ("Databases", "Databases")),
        ("Books/Loose.pdf", (None, None)),
        ("Inbox/1_Cat/Topic/Book.pdf", (None, None)),
    ],
)
def test_expected_display_from_file_path(file_path: str, expected: tuple[str | None, str | None]) -> None:
    assert expected_display_from_file_path(file_path) == expected


@pytest.mark.parametrize(
    ("size_bytes", "text"),
    [
        (0, "0 B"),
        (1023, "1023 B"),
        (1024, "1 KB"),
        (500 * 1024, "500 KB"),
        (1024 * 1024, "1.0 MB"),
        (int(2.5 * 1024 * 1024), "2.5 MB"),
    ],
)
def test_format_size(size_bytes: int, text: str) -> None:
    assert format_size(size_bytes) == text


def test_sanitize_filename_and_cover_filename() -> None:
    assert sanitize_filename("  Clean Code: A Handbook!  ") == "Clean_Code_A_Handbook"
    assert cover_filename("Clean Code") == "Clean_Code.webp"
    assert len(sanitize_filename("x" * 300)) == 100


def test_generate_book_id_is_stable_and_short() -> None:
    first = generate_book_id("Books/1_Programming/Python/Fluent_Python.pdf")
    assert first == generate_book_id("Books/1_Programming/Python/Fluent_Python.pdf")
    assert len(first) == 12
    assert first != generate_book_id("Books/1_Programming/Python/Effective_Python.pdf")


def test_detect_cover_collisions() -> None:
    books = [{"title": "Clean Code"}, {"title": "Clean_Code"}, {"title": "Refactoring"}]
    assert detect_cover_collisions(books) == {"Clean_Code.webp": ["Clean Code", "Clean_Code"]}
