#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
from pathlib import Path

from lib.book_paths import generate_book_id
from lib.cli_common import (
    EXIT_FAILURE,
    EXIT_OK,
    add_base_dir_arg,
    add_json_arg,
    add_mode_args,
    confirm,
    execute_command,
    json_mode,
    run_main,
)
from lib.constants import BOOK_EXTENSIONS, BOOKS_DIR, DATA_JSON, DEFAULT_RELEASE_TAG, INBOX_DIR
from lib.json_io import load_books, save_books
from lib.output import emit_json

COMMAND_NAME = "rename"
SCAN_DIRS = [BOOKS_DIR, INBOX_DIR]
TRANSLITERATIONS = str.maketrans({
    "đ": "d", "Đ": "D",
    "ß": "ss",
    "ø": "o", "Ø": "O",
    "æ": "ae", "Æ": "AE",
    "œ": "oe", "Œ": "OE",
    "ł": "l", "Ł": "L",
})


def remove_diacritics(text: str) -> str:
    text = text.translate(TRANSLITERATIONS)
    nfkd = unicodedata.normalize('NFD', text)
    return ''.join(c for c in nfkd if unicodedata.category(c) != 'Mn')


def slugify_filename(filename: str) -> str:
    stem = Path(filename).stem
    ext = Path(filename).suffix.lower()

    stem = remove_diacritics(stem)

    stem = re.sub(r'[\s.\-+\(\)\[\],;:!?@#$%^&*={}|\\/<>\'"~`]', '_', stem)

    stem = re.sub(r'[^a-zA-Z0-9_]', '_', stem)

    stem = re.sub(r'_+', '_', stem)

    stem = stem.strip('_')

    if not stem:
        return filename

    return f"{stem}{ext}"


def scan_and_plan(base_dir: Path) -> list[dict]:
    plan = []

    for scan_dir_name in SCAN_DIRS:
        scan_dir = base_dir / scan_dir_name
        if not scan_dir.exists():
            continue

        for root, _dirs, files in os.walk(scan_dir):
            root_path = Path(root)
            for filename in sorted(files):
                file_path = root_path / filename
                if file_path.suffix.lower() not in BOOK_EXTENSIONS:
                    continue

                new_name = slugify_filename(filename)

                if new_name != filename:
                    new_path = root_path / new_name
                    plan.append({
                        "old_path": file_path,
                        "new_path": new_path,
                        "old_name": filename,
                        "new_name": new_name,
                        "old_rel": file_path.relative_to(base_dir).as_posix(),
                        "new_rel": new_path.relative_to(base_dir).as_posix(),
                        "collision": None,
                    })

    mark_collisions(plan)
    return plan


def target_key(path: Path) -> str:
    return path.as_posix().casefold()


def mark_collisions(plan: list[dict]) -> None:
    sources_by_target: dict[str, list[dict]] = {}
    for item in plan:
        sources_by_target.setdefault(target_key(item["new_path"]), []).append(item)

    for items in sources_by_target.values():
        if len(items) > 1:
            names = ", ".join(item["old_rel"] for item in items)
            for item in items:
                item["collision"] = f"{len(items)} files would be renamed to {item['new_rel']}: {names}"

    for item in plan:
        new_path = item["new_path"]
        if item["collision"] is None and new_path.exists() and not new_path.samefile(item["old_path"]):
            item["collision"] = f"target already exists: {item['new_rel']}"


def entries_losing_download_url(books: list[dict], plan: list[dict]) -> list[dict]:
    renamed_paths = {item["old_rel"]: item["new_rel"] for item in plan if item["collision"] is None}
    return [
        {
            "id": entry.get("id"),
            "title": entry.get("title"),
            "file_path": entry.get("file_path"),
            "new_file_path": renamed_paths[entry["file_path"]],
            "download_url": entry.get("download_url"),
        }
        for entry in books
        if entry.get("file_path") in renamed_paths and entry.get("download_url")
    ]


def update_data_json(base_dir: Path, books: list[dict], renamed_items: list[dict]) -> int:
    path_map = {item["old_rel"]: item["new_rel"] for item in renamed_items}

    updated = 0
    for entry in books:
        old_fp = entry.get("file_path", "")
        if old_fp in path_map:
            entry["file_path"] = path_map[old_fp]
            entry["id"] = generate_book_id(entry["file_path"])
            entry["download_url"] = ""
            updated += 1

    if updated:
        save_books(base_dir, books, backup=True)

    return updated


def rename_file(old_path: Path, new_path: Path) -> None:
    if new_path.exists() and not new_path.samefile(old_path):
        raise FileExistsError(f"target exists: {new_path.name}")
    if new_path.exists():
        temporary = old_path.with_name(f".{old_path.name}.renaming")
        old_path.rename(temporary)
        temporary.rename(new_path)
        return
    old_path.rename(new_path)


def print_plan(plan: list[dict]) -> None:
    print(f"📋 Found {len(plan)} files to rename:\n")
    for index, item in enumerate(plan, 1):
        print(f"  {index:2d}. ❌ {item['old_name']}")
        print(f"      ✅ {item['new_name']}")
        if item["collision"]:
            print(f"      ⚠️  COLLISION, will be skipped: {item['collision']}")
        print()


def print_cleared_download_urls(cleared: list[dict]) -> None:
    if not cleared:
        return
    print(f"🔗 {len(cleared)} data.json entr{'y' if len(cleared) == 1 else 'ies'} will lose download_url "
          "(re-upload needed):")
    for entry in cleared:
        print(f"   - {entry['title']} ({entry['file_path']})")
    print()


def load_books_if_present(base_dir: Path) -> list[dict] | None:
    if not (base_dir / DATA_JSON).exists():
        return None
    return load_books(base_dir)


def run_rename(base_dir: Path, *, execute: bool, assume_yes: bool, argv: list[str]) -> dict:
    print("=" * 60)
    print("📚 My Bookshelves — Book File Renamer")
    print("=" * 60)
    print(f"📂 Base directory: {base_dir}")
    print(f"🔧 Mode: {'🚀 EXECUTE' if execute else '👀 DRY-RUN (preview only)'}\n")

    try:
        books = load_books_if_present(base_dir)
    except ValueError as exc:
        print(f"❌ Cannot read {DATA_JSON}: {exc}")
        print("   No files were renamed.")
        return {"ok": False, "error": f"Cannot read {DATA_JSON}: {exc}", "renamed": 0}

    plan = scan_and_plan(base_dir)
    collisions = [item for item in plan if item["collision"]]
    cleared = entries_losing_download_url(books or [], plan)

    if not plan:
        print("✅ All filenames are already normalized! Nothing to rename.")
        return {"ok": True, "dry_run": not execute, "planned": 0, "renamed": 0, "download_url_cleared": []}

    print_plan(plan)
    print_cleared_download_urls(cleared)
    if collisions:
        print(f"⚠️  {len(collisions)} file(s) collide and will be skipped; rename them by hand first.\n")

    if not execute:
        rerun_command = execute_command(COMMAND_NAME, argv)
        print("─" * 60)
        print("ℹ️  DRY-RUN mode. No files were renamed.")
        print("   To execute, run:")
        print(f"   {rerun_command}")
        return {
            "ok": True,
            "dry_run": True,
            "planned": len(plan),
            "collisions": len(collisions),
            "renames": plan,
            "download_url_cleared": cleared,
            "execute_command": rerun_command,
        }

    if books is None:
        print(f"⚠️  {DATA_JSON} not found; renaming files without updating it.\n")

    renamable = [item for item in plan if not item["collision"]]
    if not renamable:
        print("❌ Every planned rename collides. Nothing was renamed.")
        return {"ok": False, "dry_run": False, "planned": len(plan), "collisions": len(collisions), "renamed": 0,
                "renames": plan, "download_url_cleared": []}

    if not confirm(f"Rename {len(renamable)} file(s)?", assume_yes=assume_yes):
        print("\n❌ Cancelled. No files were renamed.")
        return {"ok": False, "cancelled": True, "renamed": 0}

    print("─" * 60)
    print("🚀 Executing renames...\n")

    renamed_items = []
    errors = 0
    updated = 0

    try:
        for item in renamable:
            try:
                rename_file(item["old_path"], item["new_path"])
            except OSError as e:
                print(f"  ⚠️  SKIP {item['old_name']}: {e}")
                errors += 1
                continue
            print(f"  ✅ {item['old_name']} → {item['new_name']}")
            renamed_items.append(item)
    finally:
        if books is not None and renamed_items:
            print(f"\n{'─' * 60}")
            print("📝 Updating data.json...")
            updated = update_data_json(base_dir, books, renamed_items)
            print(f"   ✅ Updated {updated} entries (file_path + id, cleared download_url)")

    renamed_paths = {item["old_rel"] for item in renamed_items}
    cleared_done = [entry for entry in cleared if entry["file_path"] in renamed_paths]

    print(f"\n{'═' * 60}")
    print("📊 Summary:")
    print(f"   ✅ Renamed:  {len(renamed_items)} files")
    if errors:
        print(f"   ⚠️  Skipped:  {errors}")
    if collisions:
        print(f"   ⚠️  Collisions skipped: {len(collisions)}")
    print(f"   📝 Updated:  {updated} data.json entries")
    print("\n   📌 Next steps:")
    print("   1. ./book upload --execute                           # Re-upload entries whose download_url was cleared")
    print(f"   2. (optional) gh release delete-asset {DEFAULT_RELEASE_TAG} <old_name>   # Remove old assets")
    print("   3. git add -A && git commit && git push               # Deploy")
    print(f"{'═' * 60}")

    return {
        "ok": errors == 0 and not collisions,
        "dry_run": False,
        "planned": len(plan),
        "renamed": len(renamed_items),
        "skipped": errors,
        "collisions": len(collisions),
        "data_json_updated": updated,
        "renames": renamed_items,
        "download_url_cleared": cleared_done,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=os.environ.get("BOOK_PROG"),
        description="📚 Normalize book filenames to ASCII-safe, underscore-separated format",
    )
    add_base_dir_arg(parser)
    add_mode_args(parser, execute_help="Actually rename files (default: dry-run preview)")
    add_json_arg(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    raw_args = sys.argv[1:] if argv is None else argv
    args = build_parser().parse_args(raw_args)
    base_dir = Path(args.base_dir).resolve()

    with json_mode(args.json):
        try:
            result = run_rename(base_dir, execute=args.execute, assume_yes=args.yes, argv=raw_args)
        except OSError as exc:
            print(f"\n❌ {exc}")
            result = {"ok": False, "error": str(exc)}

    if args.json:
        emit_json(result)
    return EXIT_OK if result["ok"] else EXIT_FAILURE


if __name__ == "__main__":
    run_main(main)
