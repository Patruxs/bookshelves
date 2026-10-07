#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from lib.cli_common import (
    EXIT_FAILURE,
    EXIT_OK,
    add_base_dir_arg,
    add_json_arg,
    add_mode_args,
    confirm,
    execute_command,
    json_mode,
    refresh_structure_log,
    run_main,
)
from lib.constants import BACKUP_DIR, BOOKS_DIR, COVER_DIR, DATA_JSON
from lib.json_io import load_books, save_books
from lib.output import emit_json
from lib.selection import (
    SelectionError,
    build_library_tree,
    list_library,
    remove_empty_parents,
    resolve_selection,
)

COMMAND_NAME = "delete"


class DeleteError(Exception):
    pass


@dataclass
class DeletePlan:
    covers: list[Path] = field(default_factory=list)
    files: list[Path] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)


def load_data(base_dir: Path) -> list[dict]:
    data_path = base_dir / DATA_JSON
    if not data_path.exists():
        raise DeleteError(f"data.json not found at: {data_path}")
    return load_books(base_dir)


def display_books_to_delete(books_to_delete: list[dict]) -> None:
    print(f"\n🗑️  Books to be deleted ({len(books_to_delete)}):\n")

    grouped: dict[str, dict[str, list[dict]]] = {}
    for book in books_to_delete:
        category = book.get("category", "Unknown")
        topic = book.get("topic", "Unknown")
        grouped.setdefault(category, {}).setdefault(topic, []).append(book)

    for category in sorted(grouped):
        print(f"  📂 {category}")
        for topic in sorted(grouped[category]):
            print(f"     📌 {topic}")
            for book in grouped[category][topic]:
                title = book.get("title", "Unknown").replace("_", " ")
                print(f"        🗑️  {title} [{book.get('format', '?')}] (id: {book.get('id', '?')})")
        print()


def books_without_download_url(books: list[dict]) -> list[dict]:
    return [book for book in books if not book.get("download_url")]


def remove_entries(books: list[dict], books_to_delete: list[dict]) -> list[dict]:
    selected = {id(book) for book in books_to_delete}
    return [book for book in books if id(book) not in selected]


def resolve_inside(base_dir: Path, relative_path: str, root: Path) -> Path | None:
    if not relative_path:
        return None
    candidate = (base_dir / relative_path).resolve()
    resolved_root = root.resolve()
    if candidate == resolved_root or not candidate.is_relative_to(resolved_root):
        return None
    return candidate


def plan_cover_deletions(base_dir: Path, books_to_delete: list[dict], remaining_books: list[dict]) -> list[Path]:
    remaining_covers = {book.get("cover") for book in remaining_books if book.get("cover")}
    covers: list[Path] = []
    for cover in sorted({book.get("cover") for book in books_to_delete if book.get("cover")}):
        if cover in remaining_covers:
            continue
        cover_path = resolve_inside(base_dir, cover, base_dir / COVER_DIR)
        if cover_path is not None and cover_path.is_file():
            covers.append(cover_path)
    return covers


def plan_file_deletions(base_dir: Path, books_to_delete: list[dict]) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    skipped: list[str] = []
    books_root = base_dir / BOOKS_DIR
    for book in books_to_delete:
        file_path = book.get("file_path") or ""
        resolved = resolve_inside(base_dir, file_path, books_root)
        if resolved is None:
            skipped.append(f"{file_path!r} is not inside {BOOKS_DIR}/")
        elif resolved.is_dir():
            skipped.append(f"{file_path!r} is a directory")
        elif resolved.is_file():
            files.append(resolved)
    return files, skipped


def build_plan(base_dir: Path, books_to_delete: list[dict], remaining_books: list[dict], delete_files: bool) -> DeletePlan:
    plan = DeletePlan(covers=plan_cover_deletions(base_dir, books_to_delete, remaining_books))
    if delete_files:
        plan.files, plan.skipped_files = plan_file_deletions(base_dir, books_to_delete)
    return plan


def print_plan(base_dir: Path, plan: DeletePlan, verb: str) -> None:
    for cover_path in plan.covers:
        print(f"  🖼️  {verb} cover: {cover_path.name}")
    for file_path in plan.files:
        print(f"  📄 {verb} file: {file_path.relative_to(base_dir.resolve()).as_posix()}")
    for reason in plan.skipped_files:
        print(f"  ⚠️  Skipping file: {reason}")


def make_cover_backup_dir(base_dir: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return base_dir / BACKUP_DIR / f"covers_{stamp}"


def backup_covers(base_dir: Path, covers: list[Path]) -> tuple[list[Path], list[str], Path]:
    backup_dir = make_cover_backup_dir(base_dir)
    moved: list[Path] = []
    failures: list[str] = []
    for cover_path in covers:
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(cover_path), str(backup_dir / cover_path.name))
        except OSError as exc:
            failures.append(f"{cover_path.name}: {exc}")
            print(f"  ❌ Failed to move cover {cover_path.name}: {exc}")
            continue
        moved.append(cover_path)
        print(f"  ✅ Moved cover to backup: {cover_path.name}")
    return moved, failures, backup_dir


def relative_posix(base_dir: Path, path: Path) -> str:
    return path.relative_to(base_dir.resolve()).as_posix()


def unlink_paths(base_dir: Path, paths: list[Path], label: str) -> tuple[list[Path], list[str]]:
    deleted: list[Path] = []
    failures: list[str] = []
    for path in paths:
        relative = path.relative_to(base_dir.resolve()).as_posix()
        try:
            path.unlink()
        except OSError as exc:
            failures.append(f"{relative}: {exc}")
            print(f"  ❌ Failed to delete {label} {relative}: {exc}")
            continue
        deleted.append(path)
        print(f"  ✅ Deleted {label}: {relative}")
    return deleted, failures


def cleanup_empty_dirs(base_dir: Path, deleted_files: list[Path]) -> list[Path]:
    removed = remove_empty_parents(base_dir / BOOKS_DIR, deleted_files)
    for directory in removed:
        print(f"  📁 Removed empty dir: {directory.relative_to(base_dir.resolve()).as_posix()}")
    return removed


def run_delete(args: argparse.Namespace, base_dir: Path, argv: list[str]) -> dict:
    is_dry_run = not args.execute

    print("=" * 60)
    print("📚 My Bookshelves — Book Deleter")
    print("=" * 60)
    print(f"📂 Base directory: {base_dir}")

    books = load_data(base_dir)

    if args.list:
        if args.json:
            return {"ok": True, "books": len(books), "tree": build_library_tree(books)}
        return {"ok": True, **list_library(books)}

    print(f"🔧 Mode: {'🚀 EXECUTE' if not is_dry_run else '👀 DRY-RUN (preview only)'}")
    if args.delete_files:
        print("📄 Physical files: WILL BE DELETED")
    else:
        print("📄 Physical files: kept (only data.json + covers affected)")
    print(f"\n📖 Loaded {len(books)} books from data.json")

    selection = resolve_selection(
        books,
        book=args.book,
        book_id=args.book_id,
        topic=args.topic,
        category=args.category,
        allow_partial=args.fuzzy,
        all_matches=args.all_matches,
    )
    books_to_delete = selection.books
    print(f"🔍 Selected {len(books_to_delete)} book(s){'' if selection.exact else ' (partial match)'}")
    display_books_to_delete(books_to_delete)

    if args.delete_files:
        only_copies = books_without_download_url(books_to_delete)
        if only_copies:
            listing = "\n".join(f"  - {book.get('file_path', '?')}" for book in only_copies)
            raise DeleteError(
                f"Refusing --delete-files: {len(only_copies)} selected book(s) have no download_url, "
                f"so the local file is the only copy:\n{listing}\n"
                "Upload them first (./book upload --execute) or run without --delete-files."
            )

    remaining_books = remove_entries(books, books_to_delete)
    plan = build_plan(base_dir, books_to_delete, remaining_books, args.delete_files)

    selection_report = selection.report()

    if is_dry_run:
        rerun_command = execute_command(COMMAND_NAME, argv)
        print_plan(base_dir, plan, "Would delete")
        print("─" * 60)
        print("ℹ️  DRY-RUN mode. No changes were made.")
        print("   To execute, add --execute flag:")
        print(f"   {rerun_command}")
        return {
            "ok": True,
            "dry_run": True,
            "selected": len(books_to_delete),
            **selection_report,
            "delete_files": args.delete_files,
            "books": books_to_delete,
            "covers": [path.name for path in plan.covers],
            "files": [relative_posix(base_dir, path) for path in plan.files],
            "skipped_files": plan.skipped_files,
            "execute_command": rerun_command,
        }

    print("─" * 60)
    print(f"⚠️  This will permanently delete {len(books_to_delete)} book(s) from data.json")
    if args.delete_files:
        print("   AND their physical files from the Books/ directory!")
    if not confirm("Are you sure?", assume_yes=args.yes):
        print("\n❌ Cancelled. No changes made.")
        return {"ok": False, "cancelled": True, **selection_report}

    print(f"\n{'─' * 60}")
    print("🚀 Executing deletion...\n")

    print("📝 Updating data.json...")
    save_books(base_dir, remaining_books, backup=True)
    print(f"   ✅ Removed {len(books_to_delete)} entries ({len(remaining_books)} books remaining)")

    print(f"\n📸 Moving cover images to {BACKUP_DIR}/...")
    deleted_covers, cover_failures, cover_backup_dir = backup_covers(base_dir, plan.covers)

    deleted_files: list[Path] = []
    file_failures: list[str] = []
    removed_dirs: list[Path] = []
    if args.delete_files:
        print("\n📄 Deleting physical book files...")
        for reason in plan.skipped_files:
            print(f"  ⚠️  Skipping file: {reason}")
        deleted_files, file_failures = unlink_paths(base_dir, plan.files, "file")
        print("\n📁 Cleaning up empty directories...")
        removed_dirs = cleanup_empty_dirs(base_dir, deleted_files)

    print("\n📋 Updating library_structure.log...")
    if refresh_structure_log(base_dir):
        print("  ✅ Updated library_structure.log")
    else:
        print("  ⚠️  Failed to update library_structure.log")

    failures = cover_failures + file_failures
    print(f"\n{'═' * 60}")
    print("📊 Summary:")
    print(f"   🗑️  Books removed:    {len(books_to_delete)}")
    print(f"   🖼️  Covers removed:   {len(deleted_covers)}")
    if deleted_covers:
        print(f"   💾 Cover backup:     {relative_posix(base_dir, cover_backup_dir)}")
    if args.delete_files:
        print(f"   📄 Files deleted:    {len(deleted_files)}")
        print(f"   📁 Dirs removed:     {len(removed_dirs)}")
    if failures:
        print(f"   ❌ Failed deletions: {len(failures)}")
    print(f"   📖 Books remaining:  {len(remaining_books)}")
    print("\n   📌 Next steps:")
    print("   1. git add -A && git commit -m 'Remove books' && git push")
    if args.delete_files:
        print("   2. Files on GitHub Releases are NOT deleted (do manually if needed)")
    print(f"{'═' * 60}")

    return {
        "ok": not failures,
        "dry_run": False,
        "removed": len(books_to_delete),
        **selection_report,
        "covers_deleted": len(deleted_covers),
        "cover_backup_dir": relative_posix(base_dir, cover_backup_dir) if deleted_covers else None,
        "files_deleted": len(deleted_files),
        "dirs_removed": len(removed_dirs),
        "books_remaining": len(remaining_books),
        "skipped_files": plan.skipped_files,
        "failures": failures,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=os.environ.get("BOOK_PROG"),
        description="📚 My Bookshelves — Delete books, topics, or categories",
    )

    parser.add_argument("--book", default=None,
                        help="Delete a book by exact title (use --fuzzy to accept a unique partial match)")
    parser.add_argument("--book-id", default=None, help="Delete a book by its exact ID")
    parser.add_argument("--topic", default=None, help="Delete ALL books in this exact topic (requires --category)")
    parser.add_argument("--category", default=None,
                        help="Delete ALL books in this exact category (or scope --topic to a category)")
    parser.add_argument("--fuzzy", action="store_true",
                        help="Let --book accept a unique partial title match")
    parser.add_argument("--all-matches", action="store_true",
                        help="With --fuzzy, accept a partial match that selects several different titles")

    add_mode_args(parser, execute_help="Actually perform deletion (default: dry-run preview)")
    parser.add_argument("--delete-files", action="store_true",
                        help="Also delete physical book files from Books/ (only for books that have a download_url)")

    parser.add_argument("--list", action="store_true", help="List all categories, topics, and books")
    add_json_arg(parser)
    add_base_dir_arg(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    raw_args = sys.argv[1:] if argv is None else argv
    args = build_parser().parse_args(raw_args)
    base_dir = Path(args.base_dir).resolve()

    with json_mode(args.json):
        try:
            result = run_delete(args, base_dir, raw_args)
        except (DeleteError, SelectionError, ValueError, OSError) as exc:
            print(f"\n❌ {exc}")
            result = {"ok": False, "error": str(exc)}

    if args.json:
        emit_json(result)
    return EXIT_OK if result.get("ok") else EXIT_FAILURE


if __name__ == "__main__":
    run_main(main)
