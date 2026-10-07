#!/usr/bin/env python3
from __future__ import annotations

import argparse
import http.client
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from lib.cli_common import EXIT_FAILURE, EXIT_OK, add_base_dir_arg, add_json_arg, json_mode, run_main
from lib.json_io import load_books
from lib.output import emit_json
from lib.validation import validate_library


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def validate_data(base_dir: Path, failures: list[str]) -> tuple[list[dict[str, object]], int]:
    result = validate_library(base_dir, include_dependencies=False)
    for issue in result["errors"]:
        fail(f"{issue['file']}: {issue['message']}", failures)
    if any(issue["code"] in {"missing_data_json", "invalid_json"} for issue in result["errors"]):
        return [], len(result["warnings"])
    books = [book for book in load_books(base_dir) if isinstance(book, dict)]
    return books, len(result["warnings"])


def validate_download_url_fields(
    books: list[dict[str, object]],
    failures: list[str],
    allow_missing_download_url: bool,
) -> None:
    for index, book in enumerate(books):
        label = str(book.get("title") or f"book #{index}")
        download_url = str(book.get("download_url") or "")
        if not download_url and not allow_missing_download_url:
            fail(f"{label}: missing download_url", failures)
        elif download_url:
            parsed = urlparse(download_url)
            if parsed.scheme not in {"http", "https"}:
                fail(f"{label}: download_url must be http(s), got {download_url!r}", failures)


def validate_web_sources(base_dir: Path, failures: list[str]) -> None:
    web_dir = base_dir / "web"
    required = [
        web_dir / "package.json",
        web_dir / "vite.config.ts",
        web_dir / "index.html",
        web_dir / "src" / "main.tsx",
        web_dir / "src" / "App.tsx",
    ]
    for path in required:
        if not path.exists():
            fail(f"{path.relative_to(base_dir)}: missing", failures)
    config_path = web_dir / "vite.config.ts"
    if config_path.exists():
        config = config_path.read_text(encoding="utf-8")
        if 'REPO_BASE = "/bookshelves/"' not in config:
            fail("web/vite.config.ts: REPO_BASE must be \"/bookshelves/\" for GitHub Pages", failures)
        for library_path in ('"data/data.json"', '"assets/covers"'):
            if library_path not in config:
                fail(f"web/vite.config.ts: {library_path} must ship with the build via the library-files plugin", failures)
    if (base_dir / "site").exists():
        fail("site/: retired folder still exists; data lives in data/ and covers in assets/covers/", failures)


def validate_web_dist(base_dir: Path, failures: list[str]) -> bool:
    dist_dir = base_dir / "web" / "dist"
    if not dist_dir.exists():
        return False
    index_path = dist_dir / "index.html"
    try:
        html = index_path.read_text(encoding="utf-8")
    except Exception as exc:
        fail(f"web/dist/index.html: could not read: {exc}", failures)
        return True
    scripts = re.findall(r'<script[^>]+type=["\']module["\'][^>]+src=["\']([^"\']+)["\']', html)
    if not any(src.startswith("/bookshelves/assets/") for src in scripts):
        fail("web/dist/index.html: expected a module script under /bookshelves/assets/", failures)
    if not (dist_dir / "404.html").exists():
        fail("web/dist/404.html: missing SPA fallback page", failures)
    if not (dist_dir / "data.json").exists():
        fail("web/dist/data.json: missing; library-files plugin did not copy data/data.json", failures)
    if not (dist_dir / "assets" / "covers").is_dir():
        fail("web/dist/assets/covers: missing; library-files plugin did not copy assets/covers", failures)
    return True


def validate_download_urls(books: list[dict[str, object]], failures: list[str]) -> None:
    targets: list[tuple[str, str]] = []
    for index, book in enumerate(books):
        label = str(book.get("title") or f"book #{index}")
        download_url = str(book.get("download_url") or "")
        if download_url:
            targets.append((label, download_url))

    def check(label_and_url: tuple[str, str]) -> str | None:
        label, download_url = label_and_url
        request = Request(download_url, method="HEAD", headers={"User-Agent": "my-bookshelves-smoke"})
        try:
            with urlopen(request, timeout=20) as response:
                if response.status >= 400:
                    return f"{label}: download_url returned HTTP {response.status}: {download_url}"
        except HTTPError as exc:
            return f"{label}: download_url returned HTTP {exc.code}: {download_url}"
        except URLError as exc:
            return f"{label}: download_url could not be reached: {exc.reason}: {download_url}"
        except TimeoutError:
            return f"{label}: download_url timed out: {download_url}"
        except (OSError, http.client.HTTPException) as exc:
            return f"{label}: download_url check failed: {exc}: {download_url}"
        return None

    with ThreadPoolExecutor(max_workers=12) as executor:
        for failure in executor.map(check, targets):
            if failure:
                fail(failure, failures)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke check the static site.")
    add_base_dir_arg(parser)
    add_json_arg(parser)
    parser.add_argument(
        "--allow-missing-download-url",
        action="store_true",
        help="Allow new generated books before the upload step has filled download_url",
    )
    parser.add_argument(
        "--check-download-urls",
        action="store_true",
        help="Perform network checks for each non-empty download_url",
    )
    return parser


def run_smoke_checks(args: argparse.Namespace) -> dict:
    base_dir = args.base_dir.resolve()
    failures: list[str] = []

    books, warning_count = validate_data(base_dir, failures)
    validate_download_url_fields(books, failures, args.allow_missing_download_url)
    if args.check_download_urls:
        validate_download_urls(books, failures)
    validate_web_sources(base_dir, failures)
    has_dist = validate_web_dist(base_dir, failures)
    return {
        "ok": not failures,
        "failures": failures,
        "books": len(books),
        "warnings": warning_count,
        "dist_checked": has_dist,
    }


def print_report(result: dict) -> None:
    if result["failures"]:
        print("Smoke checks failed:", file=sys.stderr)
        for failure in result["failures"]:
            print(f"- {failure}", file=sys.stderr)
        return
    dist_note = "built web/dist checked" if result["dist_checked"] else "web/dist not built, sources only"
    print(f"Smoke checks passed: {result['books']} books, web app contracts OK ({dist_note}).")
    if result["warnings"]:
        print(f"{result['warnings']} data warnings; run `book doctor` for details.")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    with json_mode(args.json):
        result = run_smoke_checks(args)
        print_report(result)
    if args.json:
        emit_json(result)
    return EXIT_OK if result["ok"] else EXIT_FAILURE


if __name__ == "__main__":
    run_main(main)
