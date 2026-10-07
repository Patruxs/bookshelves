#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from lib.book_paths import (
    display_to_folder_name,
    expected_display_from_file_path,
    generate_book_id,
    parse_category_name,
)
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
from lib.constants import BOOKS_DIR, CATEGORY_PATTERN, DATA_JSON
from lib.json_io import load_books, save_books
from lib.output import emit_json
from lib.selection import (
    Selection,
    SelectionError,
    build_library_tree,
    list_library,
    match_key,
    remove_empty_parents,
    resolve_selection,
)

COMMAND_NAME = "update"
DESCRIPTION_PREVIEW_LENGTH = 60


class UpdateError(Exception):
    pass


@dataclass(frozen=True)
class Changes:
    description: str | None = None
    category: str | None = None
    keep_category_prefix: bool = False
    topic: str | None = None
    replaced_topic: str | None = None


@dataclass(frozen=True)
class PlannedUpdate:
    book: dict
    new_file_path: str
    new_description: str | None

    @property
    def old_file_path(self) -> str:
        return self.book.get("file_path") or ""

    @property
    def moves(self) -> bool:
        return self.new_file_path != self.old_file_path

    @property
    def changes_description(self) -> bool:
        return self.new_description is not None and self.new_description != self.book.get("description")

    def updated_entry(self) -> dict:
        entry = dict(self.book)
        if self.moves:
            category, topic = expected_display_from_file_path(self.new_file_path)
            entry["id"] = generate_book_id(self.new_file_path)
            entry["category"] = category
            entry["topic"] = topic
            entry["file_path"] = self.new_file_path
        if self.new_description is not None:
            entry["description"] = self.new_description
        return entry


def load_data(base_dir: Path) -> list[dict]:
    data_path = base_dir / DATA_JSON
    if not data_path.exists():
        raise UpdateError(f"data.json not found at: {data_path}")
    return load_books(base_dir)


def topic_folders(topic: str) -> list[str]:
    return [display_to_folder_name(part.strip()) for part in topic.split("/") if part.strip()]


def category_folders(books_root: Path) -> list[str]:
    if not books_root.is_dir():
        return []
    return sorted(
        folder.name for folder in books_root.iterdir() if folder.is_dir() and CATEGORY_PATTERN.match(folder.name)
    )


def find_category_folder(books_root: Path, category: str) -> str | None:
    wanted = match_key(category)
    for folder_name in category_folders(books_root):
        if match_key(parse_category_name(folder_name)) == wanted:
            return folder_name
    return None


def next_category_number(books_root: Path) -> int:
    numbers = [int(CATEGORY_PATTERN.match(name).group(1)) for name in category_folders(books_root)]
    return max(numbers, default=0) + 1


def resolve_category_folder(books_root: Path, current_folder: str, category: str, *, keep_prefix: bool) -> str:
    existing = find_category_folder(books_root, category)
    if existing is not None and not (keep_prefix and existing == current_folder):
        return existing
    current_match = CATEGORY_PATTERN.match(current_folder)
    if keep_prefix and current_match:
        return f"{current_match.group(1)}_{display_to_folder_name(category)}"
    return f"{next_category_number(books_root)}_{display_to_folder_name(category)}"


def planned_file_path(book: dict, changes: Changes, books_root: Path) -> str:
    file_path = book.get("file_path") or ""
    parts = PurePosixPath(file_path).parts
    if len(parts) < 3 or parts[0] != BOOKS_DIR:
        raise UpdateError(f"Cannot move {book.get('title', '?')}: unsupported file_path {file_path!r}")

    category_folder = parts[1]
    topic_parts = list(parts[2:-1])
    if changes.category is not None:
        category_folder = resolve_category_folder(
            books_root, category_folder, changes.category, keep_prefix=changes.keep_category_prefix
        )
    if changes.topic is not None:
        replaced_depth = len(topic_folders(changes.replaced_topic)) if changes.replaced_topic is not None else len(topic_parts)
        topic_parts = topic_folders(changes.topic) + topic_parts[replaced_depth:]
    return PurePosixPath(BOOKS_DIR, category_folder, *topic_parts, parts[-1]).as_posix()


def plan_updates(base_dir: Path, books: list[dict], targets: list[dict], changes: Changes) -> list[PlannedUpdate]:
    books_root = base_dir / BOOKS_DIR
    plan = [
        PlannedUpdate(book, planned_file_path(book, changes, books_root), changes.description)
        for book in targets
    ]

    target_ids = {id(book) for book in targets}
    other_paths = {book.get("file_path") for book in books if id(book) not in target_ids}
    seen_paths: set[str] = set()
    for update in plan:
        if update.new_file_path in seen_paths or update.new_file_path in other_paths:
            raise UpdateError(f"Two books would end up at {update.new_file_path}")
        seen_paths.add(update.new_file_path)
        if not update.moves:
            continue
        source = base_dir / update.old_file_path
        target = base_dir / update.new_file_path
        if source.exists() and target.exists() and not target.samefile(source):
            raise UpdateError(f"Target already exists: {update.new_file_path}")
    return [update for update in plan if update.moves or update.changes_description]


def shorten(text: str) -> str:
    return text if len(text) <= DESCRIPTION_PREVIEW_LENGTH else text[:DESCRIPTION_PREVIEW_LENGTH] + "..."


def print_plan(base_dir: Path, plan: list[PlannedUpdate]) -> None:
    print(f"\n📝 Changes to be applied ({len(plan)} book(s)):\n")
    for update in plan:
        print(f"  📖 {update.book.get('title', '?').replace('_', ' ')}")
        if update.moves:
            new_category, new_topic = expected_display_from_file_path(update.new_file_path)
            local_note = "" if (base_dir / update.old_file_path).exists() else "  (not on disk; path only)"
            print(f"     move: {update.old_file_path}")
            print(f"        → {update.new_file_path}{local_note}")
            print(f"     category: \"{update.book.get('category', '')}\" → \"{new_category}\"")
            print(f"     topic: \"{update.book.get('topic', '')}\" → \"{new_topic}\"")
        if update.changes_description:
            print(f"     description: \"{shorten(update.book.get('description') or '')}\"")
            print(f"               → \"{shorten(update.new_description or '')}\"")
        print()


def rollback_moves(base_dir: Path, moves: list[tuple[Path, Path]]) -> list[str]:
    failures: list[str] = []
    for source, target in reversed(moves):
        try:
            target.rename(source)
        except OSError as exc:
            failures.append(f"{target} → {source}: {exc}")
    remove_empty_parents(base_dir / BOOKS_DIR, [target for _, target in moves])
    return failures


def move_files(base_dir: Path, plan: list[PlannedUpdate]) -> list[tuple[Path, Path]]:
    done: list[tuple[Path, Path]] = []
    for update in plan:
        if not update.moves:
            continue
        source = base_dir / update.old_file_path
        if not source.exists():
            continue
        target = base_dir / update.new_file_path
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)
        except OSError as exc:
            failures = rollback_moves(base_dir, done)
            message = f"Moving {update.old_file_path} failed: {exc}. Rolled back {len(done)} move(s); data.json untouched."
            if failures:
                message += " Rollback failures:\n" + "\n".join(failures)
            raise UpdateError(message) from exc
        done.append((source, target))
        print(f"  📦 {update.old_file_path} → {update.new_file_path}")
    return done


def change_summary(update: PlannedUpdate) -> dict:
    new_entry = update.updated_entry()
    return {
        "id": update.book.get("id"),
        "title": update.book.get("title"),
        "old_file_path": update.old_file_path,
        "new_file_path": update.new_file_path,
        "new_id": new_entry.get("id"),
        "old_category": update.book.get("category"),
        "new_category": new_entry.get("category"),
        "old_topic": update.book.get("topic"),
        "new_topic": new_entry.get("topic"),
        "description_changed": update.changes_description,
    }


def run_update(
    base_dir: Path,
    books: list[dict],
    selection: Selection,
    changes: Changes,
    *,
    execute: bool,
    assume_yes: bool,
    argv: list[str],
) -> dict:
    targets = selection.books
    plan = plan_updates(base_dir, books, targets, changes)
    summary = [change_summary(update) for update in plan]
    selection_report = {"selected": len(targets), **selection.report()}

    if not plan:
        print("\n✅ Nothing to change: the selected book(s) already match.")
        return {"ok": True, "dry_run": not execute, **selection_report, "changes": []}

    print_plan(base_dir, plan)

    if not execute:
        rerun_command = execute_command(COMMAND_NAME, argv)
        print("─" * 60)
        print("ℹ️  DRY-RUN. No changes made. To apply, run:")
        print(f"   {rerun_command}")
        return {
            "ok": True,
            "dry_run": True,
            **selection_report,
            "changes": summary,
            "execute_command": rerun_command,
        }

    if not confirm(f"Apply these changes to {len(plan)} book(s)?", assume_yes=assume_yes):
        print("\n❌ Cancelled.")
        return {"ok": False, "cancelled": True, **selection_report}

    print(f"\n{'─' * 60}")
    print("🚀 Applying updates...\n")
    moves = move_files(base_dir, plan)

    replacements = {id(update.book): update.updated_entry() for update in plan}
    updated_books = [replacements.get(id(book), book) for book in books]
    try:
        save_books(base_dir, updated_books, backup=True)
    except OSError as exc:
        failures = rollback_moves(base_dir, moves)
        message = f"Saving data.json failed: {exc}. Rolled back {len(moves)} move(s)."
        if failures:
            message += " Rollback failures:\n" + "\n".join(failures)
        raise UpdateError(message) from exc
    print(f"\n📝 Saved data.json ({len(updated_books)} books)")

    remove_empty_parents(base_dir / BOOKS_DIR, [source for source, _ in moves])

    print("\n📋 Updating library_structure.log...")
    if refresh_structure_log(base_dir):
        print("  ✅ Updated library_structure.log")
    else:
        print("  ⚠️  Failed to update library_structure.log")

    print(f"\n{'═' * 60}")
    print(f"📊 Summary: updated {len(plan)} book(s), moved {len(moves)} file(s)")
    print("\n📌 Next: git add -A && git commit -m 'Update books' && git push")
    print(f"{'═' * 60}")
    return {
        "ok": True,
        "dry_run": False,
        **selection_report,
        "updated": len(plan),
        "files_moved": len(moves),
        "changes": summary,
    }


def select_topic_tree(books: list[dict], topic: str, category: str) -> Selection:
    category_books = resolve_selection(books, category=category).books
    topic_key = match_key(topic)
    subtree = [
        book for book in category_books
        if match_key(book.get("topic")) == topic_key or match_key(book.get("topic")).startswith(topic_key + "/")
    ]
    if not subtree:
        raise SelectionError(f'No books found in topic "{topic}" of category "{category}".')
    matched_topics = tuple(dict.fromkeys(str(book.get("topic", "")) for book in subtree))
    return Selection(subtree, True, matched_topics)


def targets_and_changes(args: argparse.Namespace, books: list[dict]) -> tuple[Selection, Changes]:
    set_options = (args.set_description, args.set_category, args.set_topic)
    if args.rename is not None:
        if any(option is not None for option in set_options):
            raise UpdateError("--rename cannot be combined with --set-description/--set-category/--set-topic.")
        if args.book or args.book_id or not args.category:
            raise UpdateError("--rename requires --topic+--category or --category alone.")
        if not args.rename.strip():
            raise UpdateError("--rename needs a non-empty name.")
        if args.topic:
            selection = select_topic_tree(books, args.topic, args.category)
            return selection, Changes(topic=args.rename, replaced_topic=args.topic)
        selection = resolve_selection(books, category=args.category)
        return selection, Changes(category=args.rename, keep_category_prefix=True)

    if all(option is None for option in set_options):
        raise UpdateError("No update action. Use --set-description, --set-category, --set-topic, or --rename.")
    for flag, value in (("--set-category", args.set_category), ("--set-topic", args.set_topic)):
        if value is not None and not value.strip():
            raise UpdateError(f"{flag} needs a non-empty name.")
    selection = resolve_selection(
        books,
        book=args.book,
        book_id=args.book_id,
        topic=args.topic,
        category=args.category,
        allow_partial=args.fuzzy,
        all_matches=args.all_matches,
    )
    return selection, Changes(description=args.set_description, category=args.set_category, topic=args.set_topic)


def run_command(args: argparse.Namespace, base_dir: Path, argv: list[str]) -> dict:
    print("=" * 60)
    print("📚 My Bookshelves — Book Updater")
    print("=" * 60)
    print(f"📂 Base directory: {base_dir}")

    books = load_data(base_dir)

    if args.list:
        if args.json:
            return {"ok": True, "books": len(books), "tree": build_library_tree(books)}
        return {"ok": True, **list_library(books)}

    print(f"🔧 Mode: {'🚀 EXECUTE' if args.execute else '👀 DRY-RUN (preview only)'}")
    print(f"\n📖 Loaded {len(books)} books from data.json")

    selection, changes = targets_and_changes(args, books)
    print(f"🔍 Selected {selection.count} book(s){'' if selection.exact else ' (partial match)'}")
    return run_update(
        base_dir, books, selection, changes, execute=args.execute, assume_yes=args.yes, argv=argv
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=os.environ.get("BOOK_PROG"),
        description="📚 My Bookshelves — Update books, topics, or categories",
    )

    parser.add_argument("--book", default=None,
                        help="Select a book by exact title (use --fuzzy to accept a unique partial match)")
    parser.add_argument("--book-id", default=None, help="Select a book by exact ID")
    parser.add_argument("--topic", default=None, help="Select ALL books in this exact topic (requires --category)")
    parser.add_argument("--category", default=None, help="Select ALL books in this exact category")
    parser.add_argument("--fuzzy", action="store_true",
                        help="Let --book accept a unique partial title match")
    parser.add_argument("--all-matches", action="store_true",
                        help="With --fuzzy, accept a partial match that selects several different titles")

    parser.add_argument("--set-description", default=None,
                        help="Set new description for selected book(s); an empty string clears it")
    parser.add_argument("--set-category", default=None,
                        help="Move selected book(s) and their files to a category (existing folder is reused)")
    parser.add_argument("--set-topic", default=None,
                        help='Move selected book(s) and their files to a topic, e.g. "Programming Languages/Java"')
    parser.add_argument("--rename", default=None,
                        help="Rename a topic or category and move its files (use with --topic or --category)")

    add_mode_args(parser, execute_help="Actually perform updates (default: dry-run)")
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
            result = run_command(args, base_dir, raw_args)
        except (UpdateError, SelectionError, ValueError, OSError) as exc:
            print(f"\n❌ {exc}")
            result = {"ok": False, "error": str(exc)}

    if args.json:
        emit_json(result)
    return EXIT_OK if result.get("ok") else EXIT_FAILURE


if __name__ == "__main__":
    run_main(main)
