#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from lib.book_paths import format_size
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
from lib.constants import DATA_JSON, DEFAULT_RELEASE_TAG, SAFE_ASSET_NAME_PATTERN
from lib.json_io import load_books, save_books
from lib.output import emit_json
from lib.scanner import scan_library

GH_METADATA_TIMEOUT_SECONDS = 60
UPLOAD_BATCH_SIZE = 10
UPLOAD_MIN_TIMEOUT_SECONDS = 300
UPLOAD_MIN_BYTES_PER_SECOND = 100 * 1024
GENERATE_FIRST_REASON = "data.json and Books/ are out of sync; run ./book generate first"
GITHUB_REMOTE_PATTERN = re.compile(r"^(?:https?://|ssh://)?(?:[^@/]+@)?github\.com[:/]([^/]+)/([^/]+)$")
OWNER_REPO_PATTERN = re.compile(r"^[^/\s]+/[^/\s]+$")


class CommandError(Exception):
    pass


class UploadAborted(Exception):
    def __init__(self, message: str, details: list[str] | None = None, **extra: object) -> None:
        super().__init__(message)
        self.details = details or []
        self.extra = extra

    def summary(self) -> dict:
        return {"ok": False, "error": str(self), "details": self.details, **self.extra}


@dataclass(frozen=True)
class UploadItem:
    file_path: str
    filename: str
    abs_path: Path
    size: int


@dataclass
class UploadOutcome:
    uploaded: list[str] = field(default_factory=list)
    linked: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


def run_command(
    command: list[str],
    base_dir: Path,
    *,
    timeout: float | None = GH_METADATA_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, cwd=base_dir, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise CommandError(f"{command[0]} is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise CommandError(f"{' '.join(command)} timed out after {timeout}s") from exc


def command_error_text(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout or "").strip() or f"exit code {result.returncode}"


def check_gh_cli(base_dir: Path) -> None:
    result = run_command(["gh", "auth", "status"], base_dir)
    if result.returncode != 0:
        raise CommandError(f"GitHub CLI is not authenticated (run `gh auth login`): {command_error_text(result)}")


def parse_github_repo(remote_url: str) -> str | None:
    url = remote_url.strip().rstrip("/").removesuffix(".git")
    match = GITHUB_REMOTE_PATTERN.match(url)
    if not match:
        return None
    return f"{match.group(1)}/{match.group(2)}"


def get_repo_slug(base_dir: Path) -> str | None:
    try:
        result = run_command(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"], base_dir)
        slug = result.stdout.strip()
        if result.returncode == 0 and OWNER_REPO_PATTERN.match(slug):
            return slug
    except CommandError:
        pass
    try:
        result = run_command(["git", "remote", "get-url", "origin"], base_dir)
    except CommandError:
        return None
    if result.returncode != 0:
        return None
    return parse_github_repo(result.stdout)


def gh_release(repo_slug: str, *args: str) -> list[str]:
    return ["gh", "release", *args, "-R", repo_slug]


def release_exists(tag: str, repo_slug: str, base_dir: Path) -> bool:
    return run_command(gh_release(repo_slug, "view", tag), base_dir).returncode == 0


def create_release(tag: str, repo_slug: str, base_dir: Path) -> None:
    result = run_command(
        gh_release(
            repo_slug, "create", tag,
            "--title", f"📚 Library Storage ({tag})",
            "--notes", "Persistent storage for book files (PDF/EPUB/DOCX). Managed by upload_releases.py.",
            "--latest",
        ),
        base_dir,
    )
    if result.returncode != 0:
        raise CommandError(f"Creating release '{tag}' failed: {command_error_text(result)}")


def delete_release(tag: str, repo_slug: str, base_dir: Path) -> None:
    result = run_command(gh_release(repo_slug, "delete", tag, "--yes", "--cleanup-tag"), base_dir)
    if result.returncode != 0:
        raise CommandError(f"Deleting release '{tag}' failed: {command_error_text(result)}")


def fetch_asset_urls(tag: str, repo_slug: str, base_dir: Path) -> dict[str, str]:
    result = run_command(gh_release(repo_slug, "view", tag, "--json", "assets"), base_dir)
    if result.returncode != 0:
        raise CommandError(f"gh release view {tag} failed: {command_error_text(result)}")
    try:
        assets = json.loads(result.stdout).get("assets", [])
    except (json.JSONDecodeError, AttributeError) as exc:
        raise CommandError(f"gh release view {tag} returned unreadable JSON: {exc}") from exc
    return {asset["name"]: asset["url"] for asset in assets if asset.get("name") and asset.get("url")}


def batch_timeout(batch: list[UploadItem]) -> float:
    total_bytes = sum(item.size for item in batch)
    return max(UPLOAD_MIN_TIMEOUT_SECONDS, total_bytes / UPLOAD_MIN_BYTES_PER_SECOND)


def upload_batch(tag: str, repo_slug: str, batch: list[UploadItem], base_dir: Path, *, clobber: bool) -> str | None:
    command = gh_release(repo_slug, "upload", tag, *(str(item.abs_path) for item in batch))
    if clobber:
        command.append("--clobber")
    try:
        result = run_command(command, base_dir, timeout=batch_timeout(batch))
    except CommandError as exc:
        return str(exc)
    return None if result.returncode == 0 else command_error_text(result)


def batched(items: list[UploadItem], size: int) -> list[list[UploadItem]]:
    return [items[start:start + size] for start in range(0, len(items), size)]


def load_data(base_dir: Path) -> list[dict]:
    try:
        data = load_books(base_dir)
    except (OSError, ValueError) as exc:
        raise UploadAborted(f"Cannot read {DATA_JSON}: {exc}") from exc
    invalid = [f"entry {index}" for index, entry in enumerate(data) if not isinstance(entry, dict)]
    if invalid:
        raise UploadAborted(f"{DATA_JSON} has entries that are not objects", invalid)
    return data


def check_data_matches_disk(base_dir: Path, data: list[dict]) -> None:
    scan = scan_library(base_dir)
    data_paths = {entry.get("file_path") for entry in data}
    missing_from_data = sorted(book["rel_path"] for book in scan.books if book["rel_path"] not in data_paths)
    missing_on_disk = [
        str(entry.get("file_path") or f"entry {index} without file_path")
        for index, entry in enumerate(data)
        if not entry.get("file_path") or not (base_dir / str(entry["file_path"])).is_file()
    ]
    skipped = [skipped.path for skipped in scan.skipped]
    if missing_from_data or missing_on_disk or skipped:
        raise UploadAborted(
            GENERATE_FIRST_REASON,
            [*(f"not in data.json: {path}" for path in missing_from_data),
             *(f"no file on disk: {path}" for path in missing_on_disk),
             *(f"skipped by scanner: {path}" for path in skipped)],
            reason=GENERATE_FIRST_REASON,
            missing_from_data=missing_from_data,
            missing_on_disk=missing_on_disk,
            skipped_files=skipped,
        )


def select_uploads(base_dir: Path, data: list[dict], *, upload_all: bool) -> list[UploadItem]:
    items = []
    for entry in data:
        if not upload_all and entry.get("download_url"):
            continue
        abs_path = base_dir / str(entry["file_path"])
        items.append(UploadItem(
            file_path=str(entry["file_path"]),
            filename=abs_path.name,
            abs_path=abs_path,
            size=abs_path.stat().st_size,
        ))
    return items


def asset_name_problems(to_upload: list[UploadItem], data: list[dict]) -> list[str]:
    paths_by_filename: dict[str, list[str]] = {}
    for entry in data:
        file_path = str(entry["file_path"])
        paths_by_filename.setdefault(Path(file_path).name, []).append(file_path)
    problems = []
    for item in to_upload:
        if not re.match(SAFE_ASSET_NAME_PATTERN, item.filename):
            problems.append(f"{item.file_path}: unsafe asset name; run `./book rename --execute` first")
        if len(paths_by_filename.get(item.filename, [])) > 1:
            others = [path for path in paths_by_filename[item.filename] if path != item.file_path]
            problems.append(
                f"{item.file_path}: same filename as {', '.join(others)}; "
                "release assets share one namespace, rename one of them"
            )
    return problems


def mode_name(args: argparse.Namespace) -> str:
    if args.hard_reset:
        return "hard-reset"
    if args.force:
        return "force"
    return "incremental"


def confirm_destructive_mode(args: argparse.Namespace, upload_count: int) -> bool:
    if args.hard_reset:
        question = f"DELETE release '{args.tag}', recreate it and re-upload {upload_count} books?"
    elif args.force:
        question = f"Re-upload {upload_count} books to '{args.tag}', overwriting existing assets?"
    else:
        return True
    return confirm(question, assume_yes=args.yes)


def prepare_release(args: argparse.Namespace, repo_slug: str, base_dir: Path) -> dict[str, str]:
    exists = release_exists(args.tag, repo_slug, base_dir)
    if args.hard_reset and exists:
        print(f"🗑️  Deleting release '{args.tag}'...")
        delete_release(args.tag, repo_slug, base_dir)
        exists = False
    if not exists:
        print(f"🚀 Creating release '{args.tag}'...")
        create_release(args.tag, repo_slug, base_dir)
        return {}
    return fetch_asset_urls(args.tag, repo_slug, base_dir)


def upload_items(
    args: argparse.Namespace,
    repo_slug: str,
    base_dir: Path,
    to_upload: list[UploadItem],
    existing_assets: dict[str, str],
) -> tuple[UploadOutcome, dict[str, str]]:
    outcome = UploadOutcome()
    reupload = args.force or args.hard_reset
    pending = [item for item in to_upload if reupload or item.filename not in existing_assets]
    outcome.linked = [item.file_path for item in to_upload if item not in pending]
    for file_path in outcome.linked:
        print(f"   🔗 {Path(file_path).name}: already on the release, linking")

    failed_paths: set[str] = set()
    for batch in batched(pending, UPLOAD_BATCH_SIZE):
        names = ", ".join(item.filename for item in batch)
        print(f"   📤 Uploading {len(batch)} files ({format_size(sum(item.size for item in batch))}): {names}")
        error = upload_batch(args.tag, repo_slug, batch, base_dir, clobber=args.force)
        if error:
            print(f"   ❌ Batch failed: {error}", file=sys.stderr)
            failed_paths.update(item.file_path for item in batch)

    asset_urls = fetch_asset_urls(args.tag, repo_slug, base_dir) if pending else existing_assets
    url_map: dict[str, str] = {}
    for item in to_upload:
        url = asset_urls.get(item.filename)
        if url and item.file_path not in failed_paths:
            url_map[item.file_path] = url
            if item.file_path not in outcome.linked:
                outcome.uploaded.append(item.file_path)
        else:
            outcome.failed.append(item.file_path)
            if item.file_path not in failed_paths:
                print(f"   ❌ {item.filename}: not listed on release '{args.tag}' after upload", file=sys.stderr)
    return outcome, url_map


def apply_download_urls(base_dir: Path, data: list[dict], url_map: dict[str, str]) -> int:
    updated = 0
    for entry in data:
        url = url_map.get(str(entry.get("file_path")))
        if url and entry.get("download_url") != url:
            entry["download_url"] = url
            updated += 1
    if updated:
        save_books(base_dir, data, backup=True)
    return updated


def plan_summary(args: argparse.Namespace, data: list[dict], to_upload: list[UploadItem], argv: list[str]) -> dict:
    return {
        "ok": True,
        "dry_run": True,
        "mode": mode_name(args),
        "tag": args.tag,
        "books": len(data),
        "would_upload": len(to_upload),
        "upload_size_bytes": sum(item.size for item in to_upload),
        "files": [{"file_path": item.file_path, "size": item.size} for item in to_upload],
        "execute_command": execute_command("upload", argv),
    }


def print_plan(args: argparse.Namespace, data: list[dict], to_upload: list[UploadItem]) -> None:
    already_uploaded = sum(1 for entry in data if entry.get("download_url"))
    print(f"📋 data.json: {len(data)} entries, {already_uploaded} with download_url")
    print(f"🏷️  Release tag: {args.tag} ({mode_name(args)})")
    if args.hard_reset:
        print(f"⚠️  Hard reset deletes release '{args.tag}' and re-uploads every book.")
    if not to_upload:
        print("✅ Everything is in sync. Nothing to upload.")
        return
    upload_size = sum(item.size for item in to_upload)
    print(f"📤 To upload: {len(to_upload)} files ({format_size(upload_size)})")
    for item in to_upload:
        print(f"   {item.filename} ({format_size(item.size)})")


def upload(args: argparse.Namespace, argv: list[str]) -> tuple[int, dict]:
    base_dir = args.base_dir.resolve()
    data = load_data(base_dir)
    check_data_matches_disk(base_dir, data)

    to_upload = select_uploads(base_dir, data, upload_all=args.force or args.hard_reset)
    problems = asset_name_problems(to_upload, data)
    if problems:
        raise UploadAborted("Some files cannot be uploaded as release assets", problems)

    print_plan(args, data, to_upload)
    if not args.execute:
        print(f"🔍 DRY RUN — nothing uploaded. Run: {execute_command('upload', argv)}")
        return EXIT_OK, plan_summary(args, data, to_upload, argv)
    if not to_upload:
        return EXIT_OK, {"ok": True, "dry_run": False, "mode": mode_name(args), "tag": args.tag,
                         "uploaded": 0, "linked": 0, "failed": [], "download_urls_updated": 0}

    if not confirm_destructive_mode(args, len(to_upload)):
        print("❌ Cancelled.", file=sys.stderr)
        return EXIT_FAILURE, {"ok": False, "error": "cancelled"}

    try:
        check_gh_cli(base_dir)
        repo_slug = get_repo_slug(base_dir)
        if not repo_slug:
            raise UploadAborted("Could not detect the GitHub repository (gh repo view / git remote origin)")
        print(f"📦 Repository: {repo_slug}")
        existing_assets = prepare_release(args, repo_slug, base_dir)
        outcome, url_map = upload_items(args, repo_slug, base_dir, to_upload, existing_assets)
    except CommandError as exc:
        raise UploadAborted(str(exc)) from exc

    updated = apply_download_urls(base_dir, data, url_map)
    print(f"📝 Updated {updated} download URLs in {DATA_JSON}")
    print(f"📊 Uploaded {len(outcome.uploaded)}, linked {len(outcome.linked)}, failed {len(outcome.failed)}")
    if not outcome.failed:
        print("   Next step: git add data/data.json && git commit && git push")
    return (EXIT_FAILURE if outcome.failed else EXIT_OK), {
        "ok": not outcome.failed,
        "dry_run": False,
        "mode": mode_name(args),
        "tag": args.tag,
        "repo": repo_slug,
        "uploaded": len(outcome.uploaded),
        "linked": len(outcome.linked),
        "failed": outcome.failed,
        "download_urls_updated": updated,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Upload book files listed in data.json to GitHub Releases")
    add_base_dir_arg(parser)
    add_json_arg(parser)
    add_mode_args(parser, execute_help="Upload files and write download_url into data.json")
    parser.add_argument("--tag", default=DEFAULT_RELEASE_TAG, help=f"Release tag (default: {DEFAULT_RELEASE_TAG})")
    reset_mode = parser.add_mutually_exclusive_group()
    reset_mode.add_argument("--force", action="store_true",
                            help="Re-upload ALL books, overwriting existing assets (needs --yes)")
    reset_mode.add_argument("--hard-reset", action="store_true",
                            help="DELETE the release, recreate it and re-upload ALL books (needs --yes)")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = build_parser().parse_args(argv)
    with json_mode(args.json):
        try:
            exit_code, summary = upload(args, argv)
        except UploadAborted as exc:
            print(f"❌ {exc}", file=sys.stderr)
            for detail in exc.details:
                print(f"   - {detail}", file=sys.stderr)
            exit_code, summary = EXIT_FAILURE, exc.summary()
    if args.json:
        emit_json(summary)
    return exit_code


if __name__ == "__main__":
    run_main(main)
