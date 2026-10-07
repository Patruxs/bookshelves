import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import fitz
import pytest
from PIL import Image

from lib.book_paths import cover_filename, expected_display_from_file_path, generate_book_id
from lib.constants import COVER_DIR, DATA_JSON

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = REPO_ROOT / "scripts" / "cli.py"

FLUENT_PYTHON = "Books/1_Programming/Python/Fluent_Python.pdf"
EFFECTIVE_PYTHON = "Books/1_Programming/Python/Effective_Python.pdf"
CORE_JAVA = "Books/1_Programming/Java/Core_Java.pdf"
DATABASE_INTERNALS = "Books/2_Databases/Database_Internals.pdf"
DESIGN_PATTERNS = "Books/3_Software_Engineering/Design/Patterns/Head_First_Design_Patterns.pdf"

FIXTURE_BOOKS: dict[str, dict[str, str]] = {
    FLUENT_PYTHON: {
        "description": "Clear, concise, and effective programming.",
        "download_url": "https://example.com/releases/Fluent_Python.pdf",
    },
    EFFECTIVE_PYTHON: {"description": "90 specific ways to write better Python."},
    CORE_JAVA: {"download_url": "https://example.com/releases/Core_Java.pdf"},
    DATABASE_INTERNALS: {},
    DESIGN_PATTERNS: {"description": "A brain-friendly guide."},
}


@dataclass(frozen=True)
class CliResult:
    returncode: int
    stdout: str
    stderr: str

    def json(self) -> dict:
        return json.loads(self.stdout)


def write_pdf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    page = document.new_page(width=300, height=400)
    page.insert_text((40, 80), text)
    document.save(path)
    document.close()


def write_cover(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (60, 80), (200, 120, 40)).save(path, "WEBP")


def book_entry(file_path: str, extras: dict[str, str]) -> dict:
    category, topic = expected_display_from_file_path(file_path)
    title = Path(file_path).stem
    entry = {
        "id": generate_book_id(file_path),
        "title": title,
        "category": category,
        "topic": topic,
        "file_path": file_path,
        "cover": f"{COVER_DIR}/{cover_filename(title)}",
        "format": Path(file_path).suffix.lstrip("."),
        "description": "",
    }
    entry.update(extras)
    return entry


def read_books(base_dir: Path) -> list[dict]:
    return json.loads((base_dir / DATA_JSON).read_text(encoding="utf-8"))


def books_by_title(base_dir: Path) -> dict[str, dict]:
    return {book["title"]: book for book in read_books(base_dir)}


def run_cli(*args: str | Path) -> CliResult:
    completed = subprocess.run(
        [sys.executable, str(CLI_PATH), *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        stdin=subprocess.DEVNULL,
        timeout=120,
    )
    return CliResult(completed.returncode, completed.stdout, completed.stderr)


@pytest.fixture
def fake_library(tmp_path: Path) -> Path:
    base_dir = tmp_path / "library"
    entries = []
    for file_path, extras in FIXTURE_BOOKS.items():
        write_pdf(base_dir / file_path, Path(file_path).stem)
        entry = book_entry(file_path, extras)
        write_cover(base_dir / COVER_DIR / Path(entry["cover"]).name)
        entries.append(entry)
    (base_dir / "Inbox").mkdir()
    data_path = base_dir / DATA_JSON
    data_path.parent.mkdir(parents=True)
    data_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return base_dir
