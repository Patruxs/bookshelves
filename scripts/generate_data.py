#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from generate_structure_log import LOG_FILENAME, render_log, write_log_if_changed
from lib.book_paths import cover_filename, detect_cover_collisions, generate_book_id, normalize_text
from lib.cli_common import EXIT_FAILURE, EXIT_OK, add_base_dir_arg, add_json_arg, json_mode, run_main
from lib.constants import BOOKS_DIR, COVER_DIR, DATA_JSON
from lib.covers import dependency_status, extract_cover_with_reason
from lib.json_io import load_json, write_json_atomic
from lib.output import emit_json
from lib.scanner import scan_library

Reporter = Callable[[str], None]
MERGED_FIELDS = ("description", "download_url")


class GenerateAborted(Exception):
    pass


@dataclass
class MergeResult:
    books: list[dict] = field(default_factory=list)
    kept_stale: list[dict] = field(default_factory=list)
    dropped_stale: list[dict] = field(default_factory=list)
    moved: list[tuple[str, str]] = field(default_factory=list)
    added: list[dict] = field(default_factory=list)


@dataclass
class CoverStats:
    extracted: int = 0
    refreshed: int = 0
    skipped: int = 0
    failed: int = 0


@dataclass
class DedupeResult:
    entries: list[dict] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)


def warn(message: str) -> None:
    print(f"⚠️  {message}", file=sys.stderr)


def load_existing_books(output_path: Path) -> list[dict]:
    data = load_json(output_path, default=[])
    if not isinstance(data, list):
        raise ValueError(f"{output_path} must contain a JSON array, got {type(data).__name__}")
    for index, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise ValueError(f"{output_path} entry {index} is not an object")
    return data


def title_format_key(title: object, book_format: object) -> tuple[str, str]:
    return normalize_text(str(title or "")), str(book_format or "").lower()


def path_derived_fields(scanned_book: dict) -> dict[str, object]:
    return {
        "id": generate_book_id(scanned_book["rel_path"]),
        "title": scanned_book["title"],
        "category": scanned_book["category"],
        "topic": scanned_book["topic"],
        "file_path": scanned_book["rel_path"],
        "format": scanned_book["format"],
    }


def new_entry(scanned_book: dict) -> dict:
    fields = path_derived_fields(scanned_book)
    return {
        "id": fields["id"],
        "title": fields["title"],
        "category": fields["category"],
        "topic": fields["topic"],
        "file_path": fields["file_path"],
        "cover": "",
        "format": fields["format"],
        "description": "",
    }


def group_by_title_format(items: Iterable[dict]) -> dict[tuple[str, str], list[dict]]:
    groups: dict[tuple[str, str], list[dict]] = {}
    for item in items:
        groups.setdefault(title_format_key(item.get("title"), item.get("format")), []).append(item)
    return groups


def dedupe_by_file_path(existing: list[dict]) -> DedupeResult:
    result = DedupeResult()
    kept_by_path: dict[str, dict] = {}
    for entry in existing:
        file_path = entry.get("file_path")
        if not isinstance(file_path, str) or not file_path:
            result.entries.append(entry)
            continue
        kept = kept_by_path.get(file_path)
        if kept is None:
            kept_by_path[file_path] = entry
            result.entries.append(entry)
            continue
        for field_name in MERGED_FIELDS:
            if not kept.get(field_name) and entry.get(field_name):
                kept[field_name] = entry[field_name]
        result.duplicates.append(file_path)
    return result


def merge_entries(scanned_books: list[dict], existing: list[dict], *, prune: bool) -> MergeResult:
    existing_by_path = {
        entry["file_path"]: entry
        for entry in existing
        if isinstance(entry.get("file_path"), str) and entry.get("file_path")
    }
    scanned_by_path = {book["rel_path"]: book for book in scanned_books}

    stale = [entry for entry in existing if entry.get("file_path") not in scanned_by_path]
    unmatched = [book for book in scanned_books if book["rel_path"] not in existing_by_path]

    stale_by_key = group_by_title_format(stale)
    moved_to: dict[int, dict] = {}
    for key, books in group_by_title_format(unmatched).items():
        candidates = stale_by_key.get(key, [])
        if len(books) == 1 and len(candidates) == 1:
            moved_to[id(candidates[0])] = books[0]

    result = MergeResult()
    for entry in existing:
        scanned = scanned_by_path.get(entry.get("file_path"))
        if scanned is None and id(entry) in moved_to:
            scanned = moved_to[id(entry)]
            result.moved.append((str(entry.get("file_path")), scanned["rel_path"]))
        if scanned is not None:
            entry.update(path_derived_fields(scanned))
            result.books.append(entry)
        elif entry.get("download_url") and not prune:
            result.kept_stale.append(entry)
            result.books.append(entry)
        else:
            result.dropped_stale.append(entry)

    moved_paths = {new_path for _old_path, new_path in result.moved}
    for book in sorted(unmatched, key=lambda scanned: scanned["rel_path"]):
        if book["rel_path"] in moved_paths:
            continue
        entry = new_entry(book)
        result.added.append(entry)
        result.books.append(entry)
    return result


def cover_is_outdated(book_path: Path, cover_path: Path) -> bool:
    try:
        return book_path.stat().st_mtime > cover_path.stat().st_mtime
    except OSError:
        return False


def assign_covers(
    base_dir: Path,
    books: list[dict],
    *,
    force: bool,
    dry_run: bool,
    report: Reporter,
) -> CoverStats:
    covers_dir = base_dir / COVER_DIR
    stats = CoverStats()
    covered_this_run: set[str] = set()

    for book in books:
        title = str(book["title"])
        cover_name = cover_filename(title)
        cover_path = covers_dir / cover_name
        book_path = base_dir / str(book["file_path"])

        if not book_path.is_file():
            stats.skipped += 1
            continue
        if cover_name in covered_this_run:
            book["cover"] = f"{COVER_DIR}/{cover_name}"
            stats.skipped += 1
            continue

        outdated = cover_path.exists() and cover_is_outdated(book_path, cover_path)
        if cover_path.exists() and not force and not outdated:
            has_cover = True
            stats.skipped += 1
        elif dry_run:
            has_cover = cover_path.exists()
            report(f"  🖼️  Would {'refresh' if cover_path.exists() else 'extract'} cover: {title}")
        else:
            has_cover = extract_book_cover(book_path, cover_path, title, stats, report, refresh=outdated)

        if has_cover:
            covered_this_run.add(cover_name)
        book["cover"] = f"{COVER_DIR}/{cover_name}" if has_cover else ""
    return stats


def extract_book_cover(
    book_path: Path,
    cover_path: Path,
    title: str,
    stats: CoverStats,
    report: Reporter,
    *,
    refresh: bool,
) -> bool:
    had_cover = cover_path.exists()
    try:
        extracted, reason = extract_cover_with_reason(book_path, cover_path)
    except Exception as exc:
        extracted, reason = False, f"{type(exc).__name__}: {exc}"
    if extracted:
        if refresh:
            stats.refreshed += 1
            report(f"  🖼️  Refreshed cover (book changed): {title}")
        else:
            stats.extracted += 1
            report(f"  🖼️  Extracted cover: {title}")
        return True
    stats.failed += 1
    warn(f"Cover failed for {title}: {reason}")
    return had_cover


def find_orphan_covers(base_dir: Path, books: list[dict]) -> list[Path]:
    covers_dir = base_dir / COVER_DIR
    if not covers_dir.is_dir():
        return []
    referenced = {Path(str(book.get("cover") or "")).name for book in books}
    return sorted(
        path for path in covers_dir.iterdir()
        if path.is_file() and not path.name.startswith(".") and path.name not in referenced
    )


def serialize_books(books: list[dict]) -> str:
    return json.dumps(books, ensure_ascii=False, indent=2) + "\n"


def read_text_or_none(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate data.json and cover images for My Bookshelves")
    add_base_dir_arg(parser)
    add_json_arg(parser)
    parser.add_argument("--force", action="store_true", help="Force regenerate all cover images")
    parser.add_argument("--prune", action="store_true",
                        help="Also drop entries whose files are missing even if they have a download_url")
    parser.add_argument("--prune-covers", action="store_true",
                        help="Delete cover images that no data.json entry references")
    parser.add_argument("--dry-run", action="store_true", help="Show the result without writing covers or data")
    parser.add_argument("--quiet", action="store_true", help="Only print warnings and the summary")
    parser.add_argument("--output", default=DATA_JSON, help=f"Output JSON file (default: {DATA_JSON})")
    return parser


def generate(args: argparse.Namespace) -> dict:
    base_dir = args.base_dir.resolve()
    output_path = base_dir / args.output

    def report(message: str) -> None:
        if not args.quiet:
            print(message)

    try:
        existing = load_existing_books(output_path)
    except (OSError, ValueError) as exc:
        raise GenerateAborted(f"Cannot read {output_path}; refusing to overwrite it: {exc}") from exc

    report(f"📂 Scanning: {base_dir}")
    scan = scan_library(base_dir)
    for skipped in scan.skipped:
        warn(f"Skipped {skipped.path}: {skipped.reason}")

    if not scan.books and existing:
        raise GenerateAborted(
            f"Found 0 books under {base_dir / BOOKS_DIR} but {output_path} has {len(existing)} entries; "
            "refusing to write. Check --base-dir or restore Books/."
        )

    dedupe = dedupe_by_file_path(existing)
    for file_path in dedupe.duplicates:
        warn(f"Duplicate entry for {file_path}; merged description/download_url into the first one")

    merge = merge_entries(scan.books, dedupe.entries, prune=args.prune)
    for old_path, new_path in merge.moved:
        warn(f"moved: {old_path} -> {new_path} (description and download_url carried over)")
    for entry in merge.kept_stale:
        warn(f"Kept entry with download_url whose file is missing: {entry.get('file_path')}")
    for entry in merge.dropped_stale:
        warn(f"Dropped stale entry: {entry.get('file_path')}")
    for entry in merge.added:
        report(f"  ➕ New book: {entry['file_path']}")
    for cover, titles in detect_cover_collisions(merge.books).items():
        warn(f"Cover collision on {cover}: {', '.join(titles)}")

    if not args.dry_run:
        for name, available in dependency_status().items():
            if not available:
                warn(f"{name} is not installed; covers that need it cannot be extracted")

    cover_stats = assign_covers(base_dir, merge.books, force=args.force, dry_run=args.dry_run, report=report)

    orphan_covers = find_orphan_covers(base_dir, merge.books)
    pruned_covers: list[Path] = []
    if args.prune_covers and not args.dry_run:
        for orphan in orphan_covers:
            orphan.unlink(missing_ok=True)
            pruned_covers.append(orphan)
            report(f"  🗑️  Deleted orphan cover: {orphan.name}")
    elif orphan_covers:
        hint = "dry run" if args.prune_covers else "delete with --prune-covers"
        warn(f"{len(orphan_covers)} orphan covers not referenced by any book ({hint})")

    changed = read_text_or_none(output_path) != serialize_books(merge.books)
    backup_path = None
    structure_log_changed = False
    if not args.dry_run:
        if changed:
            backup_path = write_json_atomic(output_path, merge.books, backup=True)
        structure_log_changed = write_log_if_changed(render_log(merge.books), base_dir / LOG_FILENAME)

    ok = cover_stats.failed == 0 and not scan.skipped
    return {
        "ok": ok,
        "dry_run": args.dry_run,
        "changed": changed,
        "output": output_path,
        "books_scanned": len(scan.books),
        "books_written": len(merge.books),
        "added": len(merge.added),
        "moved": [{"from": old_path, "to": new_path} for old_path, new_path in merge.moved],
        "duplicates": len(dedupe.duplicates),
        "stale_kept": len(merge.kept_stale),
        "stale_removed": len(merge.dropped_stale),
        "skipped_files": [{"path": skipped.path, "reason": skipped.reason} for skipped in scan.skipped],
        "covers": {
            "extracted": cover_stats.extracted,
            "refreshed": cover_stats.refreshed,
            "skipped": cover_stats.skipped,
            "failed": cover_stats.failed,
        },
        "orphan_covers": [orphan.relative_to(base_dir).as_posix() for orphan in orphan_covers],
        "orphan_covers_deleted": len(pruned_covers),
        "structure_log_changed": structure_log_changed,
        "backup": backup_path,
    }


def print_summary(summary: dict) -> None:
    covers = summary["covers"]
    print(f"\n{'=' * 50}")
    print("📊 Summary:")
    print(f"   Total books found: {summary['books_scanned']}")
    print(f"   New entries:       {summary['added']}")
    print(f"   Covers extracted:  {covers['extracted']}")
    print(f"   Covers refreshed:  {covers['refreshed']}")
    print(f"   Covers failed:     {covers['failed']}")
    print(f"   Moved entries:     {len(summary['moved'])}")
    print(f"   Duplicates merged: {summary['duplicates']}")
    print(f"   Stale kept:        {summary['stale_kept']}")
    print(f"   Stale removed:     {summary['stale_removed']}")
    print(f"   Skipped files:     {len(summary['skipped_files'])}")
    print(f"   Orphan covers:     {len(summary['orphan_covers'])}")
    print(f"{'=' * 50}")
    output_path = summary["output"]
    books_written = summary["books_written"]
    if summary["dry_run"]:
        verb = "would write" if summary["changed"] else "would leave unchanged"
        print(f"🔍 DRY RUN — {verb} {output_path} ({books_written} books).")
    elif summary["changed"]:
        print(f"✅ Wrote {output_path} with {books_written} books.")
        if summary["backup"]:
            print(f"💾 Backup: {summary['backup']}")
    else:
        print(f"✅ {output_path} is up to date ({books_written} books).")
    if not summary["ok"]:
        print("❌ Some covers failed or files were skipped; see warnings above.", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    with json_mode(args.json):
        try:
            summary = generate(args)
        except GenerateAborted as exc:
            print(f"❌ {exc}", file=sys.stderr)
            summary = {"ok": False, "error": str(exc)}
        else:
            print_summary(summary)
    if args.json:
        emit_json(summary)
    return EXIT_OK if summary["ok"] else EXIT_FAILURE


if __name__ == "__main__":
    run_main(main)
