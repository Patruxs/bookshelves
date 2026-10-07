#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os

from lib.cli_common import EXIT_FAILURE, EXIT_OK, add_base_dir_arg, add_json_arg, run_main
from lib.output import emit_json
from lib.validation import validate_library


def doctor_failed(result: dict, *, strict: bool) -> bool:
    return bool(result["errors"]) or (strict and bool(result["warnings"]))


def report_mode(*, strict: bool, advisory: bool) -> str:
    if strict:
        return "strict"
    if advisory:
        return "advisory"
    return "default"


def print_human(result: dict, *, strict: bool, advisory: bool) -> None:
    summary = result["summary"]
    print("=" * 60)
    print("My Bookshelves Doctor")
    print("=" * 60)
    print(f"Base dir: {summary['base_dir']}")
    print(f"Books: {summary['books']}")
    print(f"Errors: {summary['errors']}")
    print(f"Warnings: {summary['warnings']}")
    print(f"Missing download_url: {summary['missing_download_urls']}")
    print(f"Mode: {report_mode(strict=strict, advisory=advisory)}")

    for section in ("errors", "warnings"):
        items = result[section]
        if not items:
            continue
        print()
        print(section.upper())
        for item in items:
            print(f"- [{item['code']}] {item['message']} ({item['file']})")

    environment = result.get("environment", [])
    if environment:
        print()
        print("ENVIRONMENT")
        for line in environment:
            print(f"- {line}")

    print()
    print("Status:", "FAILED" if doctor_failed(result, strict=strict) else "OK")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=os.environ.get("BOOK_PROG"),
        description="Validate the My Bookshelves repo and automation environment.",
    )
    add_base_dir_arg(parser)
    add_json_arg(parser)
    exit_mode = parser.add_mutually_exclusive_group()
    exit_mode.add_argument("--strict", action="store_true", help="Also fail on warnings")
    exit_mode.add_argument("--advisory", action="store_true", help="Always exit 0, even on errors")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    result = validate_library(args.base_dir.resolve(), include_dependencies=True)
    failed = doctor_failed(result, strict=args.strict)
    if args.json:
        emit_json({
            **result,
            "ok": not failed,
            "strict_ok": not doctor_failed(result, strict=True),
            "mode": report_mode(strict=args.strict, advisory=args.advisory),
        })
    else:
        print_human(result, strict=args.strict, advisory=args.advisory)

    if failed and not args.advisory:
        return EXIT_FAILURE
    return EXIT_OK


if __name__ == "__main__":
    run_main(main)
