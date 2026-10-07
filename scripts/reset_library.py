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
    run_main,
)
from lib.constants import BACKUP_DIR, BOOKS_DIR, COVER_DIR, DATA_JSON, INBOX_DIR
from lib.json_io import load_books, save_books
from lib.output import emit_json

COMMAND_NAME = "reset"
STRUCTURE_LOG = "library_structure.log"
COVER_SUFFIXES = {".webp", ".jpg", ".jpeg", ".png"}


@dataclass
class ResetPlan:
    backup_dir: Path
    data_json: Path | None = None
    book_count: int = 0
    covers: list[Path] = field(default_factory=list)
    structure_log: Path | None = None

    @property
    def is_empty(self) -> bool:
        return self.data_json is None and not self.covers and self.structure_log is None


def make_reset_backup_dir(base_dir: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return base_dir / BACKUP_DIR / f"reset_{stamp}"


def move_into(path: Path, destination_dir: Path) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(destination_dir / path.name))


def relative_posix(base_dir: Path, path: Path) -> str:
    return path.relative_to(base_dir).as_posix()


def build_reset_plan(base_dir: Path) -> ResetPlan:
    plan = ResetPlan(backup_dir=make_reset_backup_dir(base_dir))
    data_json = base_dir / DATA_JSON
    if data_json.exists():
        plan.data_json = data_json
        try:
            plan.book_count = len(load_books(base_dir))
        except ValueError:
            plan.book_count = 0
    covers_dir = base_dir / COVER_DIR
    if covers_dir.is_dir():
        plan.covers = sorted(
            item for item in covers_dir.iterdir() if item.is_file() and item.suffix.lower() in COVER_SUFFIXES
        )
    structure_log = base_dir / STRUCTURE_LOG
    if structure_log.exists():
        plan.structure_log = structure_log
    return plan


def print_reset_plan(base_dir: Path, plan: ResetPlan, verb: str) -> None:
    destination = relative_posix(base_dir, plan.backup_dir)
    print(f"🧹 {verb} into {destination}/:")
    if plan.data_json is not None:
        print(f"   📝 {DATA_JSON} ({plan.book_count} books), then write an empty {DATA_JSON}")
    if plan.covers:
        print(f"   🖼️  {len(plan.covers)} cover image(s) from {COVER_DIR}/")
    if plan.structure_log is not None:
        print(f"   📋 {STRUCTURE_LOG}")
    if plan.is_empty:
        print("   (nothing to move)")
    print(f"   📁 Books/ and {INBOX_DIR}/ are kept and created if missing")


def plan_summary(base_dir: Path, plan: ResetPlan) -> dict:
    return {
        "backup_dir": relative_posix(base_dir, plan.backup_dir),
        "data_json": plan.data_json is not None,
        "books": plan.book_count,
        "covers": [cover.name for cover in plan.covers],
        "structure_log": plan.structure_log is not None,
    }


def reset_library(base_dir: Path, plan: ResetPlan) -> None:
    print("🧹 Cleaning up current data for a fresh start...")
    if plan.data_json is not None:
        move_into(plan.data_json, plan.backup_dir)
    save_books(base_dir, [], backup=True)
    print(f"   ✅ Reset {DATA_JSON} to empty")

    for cover in plan.covers:
        move_into(cover, plan.backup_dir / "covers")
    if plan.covers:
        print(f"   ✅ Moved {len(plan.covers)} cover image(s) aside")

    if plan.structure_log is not None:
        move_into(plan.structure_log, plan.backup_dir)
        print(f"   ✅ Moved {STRUCTURE_LOG} aside")

    (base_dir / BOOKS_DIR).mkdir(exist_ok=True)
    (base_dir / INBOX_DIR).mkdir(exist_ok=True)

    if plan.backup_dir.exists():
        print(f"   💾 Previous data kept in {relative_posix(base_dir, plan.backup_dir)}")
    print("\n✨ Library has been successfully reset. You are ready to add your own books!")


def run_reset(base_dir: Path, *, execute: bool, assume_yes: bool, argv: list[str]) -> dict:
    plan = build_reset_plan(base_dir)
    summary = plan_summary(base_dir, plan)

    if not execute:
        rerun_command = execute_command(COMMAND_NAME, argv)
        print_reset_plan(base_dir, plan, "Would move")
        print("\nℹ️  DRY-RUN. Nothing was moved. To reset, run:")
        print(f"   {rerun_command}")
        return {"ok": True, "dry_run": True, **summary, "execute_command": rerun_command}

    print_reset_plan(base_dir, plan, "Will move")
    if not confirm("⚠️  Move all current book metadata and covers to .backups/?", assume_yes=assume_yes):
        print("Operation cancelled.")
        return {"ok": False, "cancelled": True}

    reset_library(base_dir, plan)
    return {"ok": True, "dry_run": False, **summary}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=os.environ.get("BOOK_PROG"),
        description="Move current metadata and covers to .backups/ (fresh start).",
    )
    add_mode_args(parser, execute_help="Actually move data.json, covers and the structure log to .backups/")
    parser.add_argument("--force", action="store_true", help=argparse.SUPPRESS)
    add_json_arg(parser)
    add_base_dir_arg(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    raw_args = sys.argv[1:] if argv is None else argv
    args = build_parser().parse_args(raw_args)
    base_dir = Path(args.base_dir).resolve()
    execute = args.execute or (args.force and not args.dry_run)
    assume_yes = args.yes or args.force

    with json_mode(args.json):
        try:
            result = run_reset(base_dir, execute=execute, assume_yes=assume_yes, argv=raw_args)
        except OSError as exc:
            print(f"❌ {exc}")
            result = {"ok": False, "error": str(exc)}

    if args.json:
        emit_json(result)
    return EXIT_OK if result.get("ok") else EXIT_FAILURE


if __name__ == "__main__":
    run_main(main)
