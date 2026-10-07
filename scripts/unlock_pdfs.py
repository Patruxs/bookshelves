#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType

from lib.cli_common import EXIT_FAILURE, run_main
from lib.constants import BACKUP_DIR
from lib.covers import import_pymupdf
from lib.inbox_jobs import (
    ConversionPlan,
    InboxJob,
    Outcome,
    add_inbox_args,
    confirm_execution,
    finish,
    report_error,
    resolve_inbox_dir,
    run_plan,
    select_sources,
)

UNLOCK_PDFS = InboxJob(
    title="My Bookshelves PDF Unlocker",
    source_suffix=".pdf",
    target_suffix=".pdf",
    action="Remove PDF encryption",
    execute_hint="Add --execute to replace encrypted PDFs.",
)

DEDICATED_PASSWORD_FILE = ".env.pdf-unlock"
PROJECT_ENV_FILE = ".env"
PASSWORD_ENV_VARS = ("PDF_UNLOCK_PASSWORD", "PDF_PASSWORD")
ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
INLINE_COMMENT_PATTERN = re.compile(r"\s+#")


def import_fitz() -> ModuleType:
    fitz = import_pymupdf()
    if fitz is None:
        raise RuntimeError(
            "PyMuPDF is required. Install dependencies with: "
            "python -m pip install -r requirements.txt"
        )
    return fitz


def parse_env_value(raw_value: str) -> str:
    value = raw_value.strip()
    if value[:1] in ("'", '"'):
        closing = value.find(value[0], 1)
        if closing > 0:
            return value[1:closing]
    return INLINE_COMMENT_PATTERN.split(value, maxsplit=1)[0].strip()


def parse_password_assignment(line: str) -> str | None:
    body = line.removeprefix("export").lstrip() if re.match(r"export\s", line) else line
    key, separator, value = body.partition("=")
    key = key.strip()
    if not separator or not ENV_KEY_PATTERN.match(key) or key not in PASSWORD_ENV_VARS:
        return None
    return parse_env_value(value)


def read_password_file(path: Path, *, allow_raw: bool = True) -> str:
    raw_candidates: list[str] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        password = parse_password_assignment(stripped)
        if password:
            return password
        if password is None:
            raw_candidates.append(stripped)

    if allow_raw and raw_candidates:
        return raw_candidates[0]

    raise ValueError(f"Password file is empty or missing {PASSWORD_ENV_VARS[0]}")


def resolve_password(
    base_dir: Path,
    password_file: str | None,
    *,
    prompt: bool,
) -> tuple[str | None, str]:
    if password_file:
        path = Path(password_file)
        if not path.is_absolute():
            path = base_dir / path
        if not path.exists():
            raise FileNotFoundError(f"Password file not found: {path}")
        return read_password_file(path), str(path)

    for env_var in PASSWORD_ENV_VARS:
        password = os.environ.get(env_var)
        if password:
            return password, f"environment variable {env_var}"

    for name, allow_raw in ((DEDICATED_PASSWORD_FILE, True), (PROJECT_ENV_FILE, False)):
        default_path = base_dir / name
        if default_path.exists():
            try:
                return read_password_file(default_path, allow_raw=allow_raw), str(default_path)
            except ValueError:
                continue

    if prompt:
        if not sys.stdin.isatty():
            raise RuntimeError(
                "No password source found. Set PDF_UNLOCK_PASSWORD, or create "
                f"{DEDICATED_PASSWORD_FILE} / {PROJECT_ENV_FILE} with "
                f"{PASSWORD_ENV_VARS[0]}=... locally."
            )
        password = getpass.getpass("PDF password: ")
        if not password:
            raise RuntimeError("Password cannot be empty")
        return password, "interactive prompt"

    return None, "not provided"


def has_encryption(doc) -> bool:
    return bool(doc.needs_pass or doc.metadata.get("encryption"))


def inspect_pdf(fitz: ModuleType, pdf_path: Path, password: str | None) -> Outcome:
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        return Outcome("failed", f"Cannot open PDF: {exc}")

    try:
        if not doc.needs_pass:
            if has_encryption(doc):
                return Outcome("planned", "Owner-password restrictions can be removed")
            return Outcome("skipped", "PDF is not password-protected")

        if password is None:
            return Outcome("planned", "Password-protected PDF")

        if doc.authenticate(password):
            return Outcome("planned", "Password works; PDF can be unlocked")
        return Outcome("failed", "Password did not unlock this PDF")
    finally:
        doc.close()


def make_backup_path(base_dir: Path, pdf_path: Path, batch_id: str) -> Path:
    rel_path = pdf_path.relative_to(base_dir)
    return base_dir / BACKUP_DIR / "pdf_unlock" / batch_id / rel_path


def unlock_pdf(
    fitz: ModuleType,
    pdf_path: Path,
    password: str | None,
    base_dir: Path,
    *,
    batch_id: str,
    keep_backup: bool,
) -> Outcome:
    temp_path = pdf_path.with_name(f".{pdf_path.stem}.unlocking{pdf_path.suffix}")

    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        return Outcome("failed", f"Cannot open PDF: {exc}")

    try:
        try:
            if not has_encryption(doc):
                return Outcome("skipped", "PDF is not password-protected")

            if doc.needs_pass and (password is None or not doc.authenticate(password)):
                return Outcome("failed", "Password did not unlock this PDF")

            temp_path.unlink(missing_ok=True)
            doc.save(
                temp_path,
                garbage=4,
                deflate=True,
                clean=True,
                encryption=fitz.PDF_ENCRYPT_NONE,
            )
        except Exception as exc:
            return Outcome("failed", f"Failed to write unlocked PDF: {exc}")
        finally:
            doc.close()

        try:
            verify = fitz.open(temp_path)
            try:
                if has_encryption(verify):
                    return Outcome("failed", "Unlocked output is still encrypted")
            finally:
                verify.close()

            backup_path: Path | None = None
            if keep_backup:
                backup_path = make_backup_path(base_dir, pdf_path, batch_id)
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(pdf_path, backup_path)

            os.replace(temp_path, pdf_path)
        except Exception as exc:
            return Outcome("failed", f"Failed to replace original PDF: {exc}")
    finally:
        temp_path.unlink(missing_ok=True)

    return Outcome("unlocked", "Password removed", backup_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=os.environ.get("BOOK_PROG"),
        description="Remove password encryption from PDF files in Inbox.",
    )
    add_inbox_args(parser, execute_help="Replace encrypted PDFs")
    parser.add_argument(
        "--password-file",
        help=(
            "Local password file; wins over environment variables. Supports raw password text or "
            "PDF_UNLOCK_PASSWORD=... format. Default: .env.pdf-unlock, then .env (KEY=... only)."
        ),
    )
    parser.add_argument("--no-backup", action="store_true", help="Do not keep encrypted backups")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_dir = Path(args.base_dir).resolve()

    try:
        fitz = import_fitz()
        inbox_dir = resolve_inbox_dir(base_dir, args.inbox_dir)
        plans = [
            ConversionPlan(pdf_path, pdf_path, "planned", UNLOCK_PDFS.action)
            for pdf_path in select_sources(inbox_dir, UNLOCK_PDFS.source_suffix, args.files)
        ]
    except Exception as exc:
        report_error(exc, as_json=args.json)
        return EXIT_FAILURE

    if args.execute and not confirm_execution(
        plans, "Unlock these PDF file(s) in place?", assume_yes=args.yes, as_json=args.json
    ):
        return EXIT_FAILURE

    try:
        password, password_source = resolve_password(
            base_dir,
            args.password_file,
            prompt=args.execute,
        )
    except Exception as exc:
        report_error(exc, as_json=args.json)
        return EXIT_FAILURE

    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def process_one(plan: ConversionPlan) -> Outcome:
        if args.execute:
            return unlock_pdf(
                fitz,
                plan.source,
                password,
                base_dir,
                batch_id=batch_id,
                keep_backup=not args.no_backup,
            )
        return inspect_pdf(fitz, plan.source, password)

    results = run_plan(plans, base_dir, process_one, fail_fast=args.fail_fast)
    return finish(
        results,
        UNLOCK_PDFS,
        dry_run=not args.execute,
        as_json=args.json,
        extra={"password_source": password_source},
    )


if __name__ == "__main__":
    run_main(main)
