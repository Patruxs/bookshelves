#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from lib.cli_common import (
    EXIT_FAILURE,
    EXIT_OK,
    EXIT_USAGE,
    SCRIPTS_DIR,
    add_base_dir_arg,
    add_json_arg,
    add_mode_args,
    confirm,
    execute_command,
    json_mode,
    refresh_structure_log,
    run_main,
)
from lib.constants import BOOK_EXTENSIONS, BOOKS_DIR, CATEGORY_PATTERN, DATA_JSON, INBOX_DIR
from lib.json_io import load_books
from lib.output import emit_json

FOLDER_NAME_PATTERN = re.compile(r"^[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*$")
CATEGORY_FOLDER_PATTERN = re.compile(r"^\d+_[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*$")
PLAN_FIELDS = ("file", "category", "topic", "description")

JsonObject = dict[str, Any]


@dataclass
class PlanEntry:
    index: int
    source: Path
    destination: Path
    category: str
    topic: str
    description: str

    def destination_rel(self, base_dir: Path) -> str:
        return self.destination.relative_to(base_dir).as_posix()

    def source_rel(self, base_dir: Path) -> str:
        return self.source.relative_to(base_dir).as_posix()


@dataclass
class Validation:
    entries: list[PlanEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    new_folders: list[str] = field(default_factory=list)


class StepFailed(Exception):
    pass


def load_plan(plan_path: Path) -> list[object]:
    with open(plan_path, encoding="utf-8") as plan_file:
        plan = json.load(plan_file)
    if not isinstance(plan, list):
        raise ValueError(f"{plan_path} must contain a JSON array")
    return plan


def existing_category_numbers(books_dir: Path) -> dict[str, str]:
    numbers: dict[str, str] = {}
    if not books_dir.is_dir():
        return numbers
    for folder in books_dir.iterdir():
        match = CATEGORY_PATTERN.match(folder.name)
        if folder.is_dir() and match:
            numbers[match.group(1)] = folder.name
    return numbers


def inbox_source(base_dir: Path, file_value: str) -> Path:
    relative = PurePosixPath(file_value.replace("\\", "/"))
    if relative.parts and relative.parts[0] == INBOX_DIR:
        relative = PurePosixPath(*relative.parts[1:])
    return base_dir / INBOX_DIR / Path(*relative.parts)


def existing_book_stems(books_dir: Path) -> dict[str, str]:
    if not books_dir.is_dir():
        return {}
    return {
        path.stem.lower(): path.as_posix()
        for path in books_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in BOOK_EXTENSIONS
    }


def is_filled(raw: JsonObject, name: str) -> bool:
    value = raw.get(name)
    return isinstance(value, str) and bool(value.strip())


def file_errors(base_dir: Path, file_value: str) -> list[str]:
    source = inbox_source(base_dir, file_value)
    errors = []
    if source.resolve().parent != (base_dir / INBOX_DIR).resolve():
        errors.append(f"file must be directly inside {INBOX_DIR}/: {file_value}")
    elif not source.is_file():
        errors.append(f"file not found: {source.relative_to(base_dir).as_posix()}")
    if source.suffix.lower() not in BOOK_EXTENSIONS:
        errors.append(f"unsupported file type {source.suffix or '(none)'}")
    return errors


def category_errors(category: str, category_numbers: dict[str, str]) -> list[str]:
    if not CATEGORY_FOLDER_PATTERN.match(category):
        return [f"category {category!r} must look like N_Snake_Case"]
    number = category.split("_", 1)[0]
    owner = category_numbers.get(number)
    if owner is not None and owner != category:
        return [f"category number {number} already belongs to {owner}"]
    return []


def entry_errors(base_dir: Path, raw: object, category_numbers: dict[str, str]) -> list[str]:
    if not isinstance(raw, dict):
        return ["must be an object"]
    errors = [f"{name} must be a non-empty string" for name in PLAN_FIELDS if not is_filled(raw, name)]
    if is_filled(raw, "file"):
        errors.extend(file_errors(base_dir, raw["file"]))
    if is_filled(raw, "category"):
        errors.extend(category_errors(raw["category"], category_numbers))
    if is_filled(raw, "topic") and not all(FOLDER_NAME_PATTERN.match(part) for part in raw["topic"].split("/")):
        errors.append(f"topic {raw['topic']!r} must be Snake_Case folders separated by /")
    return errors


def validate_plan(base_dir: Path, plan: list[object]) -> Validation:
    books_dir = base_dir / BOOKS_DIR
    category_numbers = existing_category_numbers(books_dir)
    known_stems = existing_book_stems(books_dir)
    validation = Validation()
    destinations: dict[Path, int] = {}
    sources: dict[Path, int] = {}
    new_folders: set[str] = set()

    for index, raw in enumerate(plan, start=1):
        problems = entry_errors(base_dir, raw, category_numbers)
        if problems:
            validation.errors.extend(f"entry {index}: {problem}" for problem in problems)
            continue
        assert isinstance(raw, dict)
        source = inbox_source(base_dir, raw["file"])
        folder = books_dir / raw["category"] / Path(*raw["topic"].split("/"))
        destination = folder / source.name
        destination_rel = destination.relative_to(base_dir).as_posix()

        if source in sources:
            validation.errors.append(f"entry {index}: {raw['file']} is already planned in entry {sources[source]}")
        sources.setdefault(source, index)
        if destination.exists():
            validation.errors.append(f"entry {index}: destination exists: {destination_rel}")
        elif destination in destinations:
            other = destinations[destination]
            validation.errors.append(f"entry {index}: destination {destination_rel} is also used by entry {other}")
        elif source.stem.lower() in known_stems:
            existing = known_stems[source.stem.lower()]
            validation.errors.append(f"entry {index}: a book named {source.stem} already exists at {existing}")
        destinations.setdefault(destination, index)

        for depth in range(1, len(folder.relative_to(books_dir).parts) + 1):
            candidate = books_dir.joinpath(*folder.relative_to(books_dir).parts[:depth])
            if not candidate.is_dir():
                new_folders.add(candidate.relative_to(base_dir).as_posix())

        validation.entries.append(
            PlanEntry(index, source, destination, raw["category"], raw["topic"], raw["description"].strip())
        )

    validation.new_folders = sorted(new_folders)
    return validation


def print_plan_table(base_dir: Path, validation: Validation) -> None:
    print("| # | File | Category -> Topic | Description |")
    print("| --- | --- | --- | --- |")
    for entry in validation.entries:
        summary = entry.description.splitlines()[0][:60]
        print(f"| {entry.index} | {entry.source.name} | {entry.category} -> {entry.topic} | {summary} |")
    if validation.new_folders:
        print("\nNew folders:")
        for folder in validation.new_folders:
            print(f"  + {folder}")
    if validation.errors:
        print("\nErrors:")
        for error in validation.errors:
            print(f"  - {error}")


def run_book_command(command: str, arguments: list[str]) -> tuple[int, JsonObject]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "cli.py"), command, *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.stderr:
        print(completed.stderr.rstrip(), file=sys.stderr)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {"ok": False, "error": completed.stdout.strip() or f"{command} printed no JSON"}
    if not isinstance(payload, dict):
        payload = {"ok": False, "error": f"{command} printed unexpected JSON"}
    return completed.returncode, payload


def move_files(base_dir: Path, entries: list[PlanEntry]) -> list[JsonObject]:
    moved: list[PlanEntry] = []
    try:
        for entry in entries:
            entry.destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(entry.source), str(entry.destination))
            moved.append(entry)
            print(f"📦 {entry.source_rel(base_dir)} -> {entry.destination_rel(base_dir)}")
    except OSError as error:
        for entry in reversed(moved):
            shutil.move(str(entry.destination), str(entry.source))
        raise StepFailed(f"move failed, moves rolled back: {error}") from error
    return [{"from": entry.source_rel(base_dir), "to": entry.destination_rel(base_dir)} for entry in moved]


def generate_data(base_dir: Path) -> JsonObject:
    returncode, payload = run_book_command("generate", ["--base-dir", str(base_dir), "--json"])
    if returncode != 0 or not payload.get("ok"):
        raise StepFailed(f"generate failed: {payload.get('error', f'exit {returncode}')}")
    return payload


def describe_books(base_dir: Path, entries: list[PlanEntry]) -> tuple[list[JsonObject], list[str]]:
    ids_by_path = {book.get("file_path"): book.get("id") for book in load_books(base_dir) if isinstance(book, dict)}
    described: list[JsonObject] = []
    failures: list[str] = []
    for entry in entries:
        file_path = entry.destination_rel(base_dir)
        book_id = ids_by_path.get(file_path)
        if not book_id:
            failures.append(f"{file_path} is missing from {DATA_JSON}")
            continue
        returncode, payload = run_book_command(
            "update",
            ["--base-dir", str(base_dir), "--book-id", book_id, "--set-description", entry.description,
             "--execute", "--yes", "--json"],
        )
        if returncode != 0 or not payload.get("ok"):
            failures.append(f"{file_path}: {payload.get('error', f'update exit {returncode}')}")
            continue
        described.append({"id": book_id, "file_path": file_path})
        print(f"📝 Described {file_path}")
    return described, failures


def issue_mentions_batch(issue: JsonObject, batch_paths: set[str], batch_locations: set[str]) -> bool:
    if issue.get("file_path") in batch_paths or issue.get("file") in batch_locations:
        return True
    text = json.dumps(issue, ensure_ascii=False)
    return any(path in text for path in batch_paths)


def run_doctor(base_dir: Path, batch_paths: set[str]) -> JsonObject:
    _, payload = run_book_command("doctor", ["--base-dir", str(base_dir), "--json"])
    reported_errors = payload.get("errors")
    errors = reported_errors if isinstance(reported_errors, list) else []
    try:
        books = load_books(base_dir)
    except (OSError, ValueError):
        books = []
    batch_locations = {
        f"{DATA_JSON} entry {index}"
        for index, book in enumerate(books)
        if isinstance(book, dict) and book.get("file_path") in batch_paths
    }
    batch_errors = [
        issue
        for issue in errors
        if isinstance(issue, dict) and issue_mentions_batch(issue, batch_paths, batch_locations)
    ]
    return {
        "ok": bool(payload.get("ok")),
        "summary": payload.get("summary", {}),
        "errors": errors,
        "batch_errors": batch_errors,
        "warnings": payload.get("warnings", []),
        "error": payload.get("error"),
    }


def execute_plan(base_dir: Path, entries: list[PlanEntry]) -> JsonObject:
    result: JsonObject = {"ok": False, "dry_run": False, "moved": [], "described": [], "doctor": None}
    try:
        result["moved"] = move_files(base_dir, entries)
        result["generate"] = generate_data(base_dir)
        result["described"], failures = describe_books(base_dir, entries)
        if failures:
            result["errors"] = failures
            raise StepFailed("describe failed: " + "; ".join(failures))
        result["structure_log"] = refresh_structure_log(base_dir)
        batch_paths = {entry.destination_rel(base_dir) for entry in entries}
        result["doctor"] = run_doctor(base_dir, batch_paths)
        if result["doctor"]["batch_errors"]:
            raise StepFailed(f"doctor reported {len(result['doctor']['batch_errors'])} error(s) for this batch")
        if not result["structure_log"]:
            raise StepFailed("could not refresh library_structure.log")
    except StepFailed as error:
        result["error"] = str(error)
        print(f"❌ {error}")
        return result
    result["ok"] = True
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=os.environ.get("BOOK_PROG"),
        description="Apply an Inbox classification plan: move, generate, describe, validate",
    )
    parser.add_argument("plan", type=Path, help="JSON plan file: [{file, category, topic, description}]")
    add_base_dir_arg(parser)
    add_mode_args(parser, execute_help="Move the files, generate data, set descriptions and run doctor")
    add_json_arg(parser)
    return parser


def run(args: argparse.Namespace, base_dir: Path, argv: list[str]) -> tuple[int, JsonObject]:
    try:
        plan = load_plan(args.plan)
    except (OSError, ValueError) as error:
        print(f"❌ Cannot read plan {args.plan}: {error}")
        return EXIT_USAGE, {"ok": False, "error": f"cannot read plan: {error}"}

    validation = validate_plan(base_dir, plan)
    print_plan_table(base_dir, validation)
    preview = {
        "ok": not validation.errors,
        "dry_run": not args.execute,
        "entries": [
            {"file": entry.source_rel(base_dir), "destination": entry.destination_rel(base_dir)}
            for entry in validation.entries
        ],
        "new_folders": validation.new_folders,
        "errors": validation.errors,
    }
    if validation.errors:
        print(f"\n❌ Plan has {len(validation.errors)} error(s); nothing was changed.")
        return EXIT_FAILURE, preview
    if not validation.entries:
        print("\n📭 Plan is empty; nothing to do.")
        return EXIT_OK, preview
    if not args.execute:
        print(f"\n👀 Dry run. Apply with: {execute_command('apply-plan', argv)}")
        return EXIT_OK, preview
    if not confirm(f"Move {len(validation.entries)} book(s) and update the library?", assume_yes=args.yes):
        print("Cancelled.")
        return EXIT_FAILURE, {**preview, "ok": False, "error": "cancelled"}

    result = execute_plan(base_dir, validation.entries)
    if result["ok"]:
        print(f"\n✅ Applied {len(result['moved'])} book(s).")
    return (EXIT_OK if result["ok"] else EXIT_FAILURE), result


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    args = build_parser().parse_args(arguments)
    base_dir = args.base_dir.resolve()
    with json_mode(args.json):
        exit_code, result = run(args, base_dir, arguments)
    if args.json:
        emit_json(result)
    return exit_code


if __name__ == "__main__":
    run_main(main)
