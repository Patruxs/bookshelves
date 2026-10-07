#!/usr/bin/env python3
from __future__ import annotations

import argparse
import functools
import os
import posixpath
import re
import shutil
import subprocess
import tempfile
import zipfile
from collections.abc import Collection, Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from urllib.parse import unquote

from lib.cli_common import EXIT_FAILURE, run_main
from lib.covers import import_pymupdf
from lib.inbox_jobs import (
    ConversionPlan,
    InboxJob,
    add_inbox_args,
    build_plan,
    confirm_execution,
    finish,
    plan_to_results,
    report_error,
    resolve_inbox_dir,
    run_plan,
)
from lib.output import make_progress_printer

EPUB_TO_PDF = InboxJob(
    title="My Bookshelves EPUB to PDF Converter",
    source_suffix=".epub",
    target_suffix=".pdf",
    action="Convert EPUB to PDF",
    execute_hint="Add --execute to create PDFs.",
)

LETTER_WIDTH = 612.0
LETTER_HEIGHT = 792.0
PAGE_MARGIN = 54.0
CALIBRE_FLATPAK_ID = "com.calibre_ebook.calibre"
CALIBRE_DEFAULT_LOCATIONS = (
    Path(r"C:\Program Files\Calibre2\ebook-convert.exe"),
    Path("/Applications/calibre.app/Contents/MacOS/ebook-convert"),
)
CALIBRE_VERSION_TIMEOUT_SECONDS = 30
CALIBRE_CONVERT_TIMEOUT_SECONDS = 30 * 60
CALIBRE_PDF_OPTIONS = [
    "--paper-size",
    "letter",
    "--pdf-page-margin-left",
    str(PAGE_MARGIN),
    "--pdf-page-margin-right",
    str(PAGE_MARGIN),
    "--pdf-page-margin-top",
    str(PAGE_MARGIN),
    "--pdf-page-margin-bottom",
    str(PAGE_MARGIN),
    "--pdf-serif-family",
    "TeX Gyre Termes",
    "--pdf-sans-family",
    "TeX Gyre Heros",
    "--pdf-mono-family",
    "TeX Gyre Cursor",
    "--pdf-standard-font",
    "serif",
    "--pdf-default-font-size",
    "12",
    "--pdf-mono-font-size",
    "10",
]
COVER_FILE_NAMES = {"cover.jpg", "cover.jpeg", "cover.png", "cover.webp"}
MAX_COVER_LIKE_PAGES = 3

_BACKGROUND_NONE_PATTERN = re.compile(
    rb"(?<![-\w])background(\s*:\s*)none"
    rb"(\s*(?:!\s*important\s*)?)(?=[;}])",
    flags=re.IGNORECASE,
)
_SCROLLING_BLOCK_PATTERN = re.compile(
    rb"display\s*:\s*block\s*(?:!\s*important\s*)?;\s*"
    rb"overflow-x(\s*:\s*)auto(\s*(?:!\s*important\s*)?)(?=[;}])",
    flags=re.IGNORECASE,
)


def import_fitz() -> ModuleType:
    fitz = import_pymupdf()
    if fitz is None:
        raise RuntimeError(
            "PyMuPDF is required. Install dependencies with: "
            "python -m pip install -r requirements.txt"
        )
    return fitz


@contextmanager
def suppress_pymupdf_messages(fitz) -> Iterator[None]:
    display_errors = fitz.TOOLS.mupdf_display_errors()
    display_warnings = fitz.TOOLS.mupdf_display_warnings()
    fitz.TOOLS.mupdf_display_errors(False)
    fitz.TOOLS.mupdf_display_warnings(False)
    try:
        yield
    finally:
        fitz.TOOLS.mupdf_display_errors(display_errors)
        fitz.TOOLS.mupdf_display_warnings(display_warnings)


def calibre_command_candidates() -> list[list[str]]:
    candidates: list[list[str]] = []
    if shutil.which("ebook-convert"):
        candidates.append(["ebook-convert"])
    candidates.extend([str(location)] for location in CALIBRE_DEFAULT_LOCATIONS if location.is_file())
    if shutil.which("flatpak"):
        candidates.append(["flatpak", "run", "--command=ebook-convert", CALIBRE_FLATPAK_ID])
    return candidates


@functools.cache
def find_calibre_command() -> list[str] | None:
    for command in calibre_command_candidates():
        try:
            result = subprocess.run(
                [*command, "--version"],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=CALIBRE_VERSION_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            return command
    return None


def command_error_tail(result: subprocess.CompletedProcess[str]) -> str:
    output = "\n".join(part for part in (result.stderr, result.stdout) if part)
    lines = output.strip().splitlines()
    if not lines:
        return f"exit code {result.returncode}"
    return "\n".join(lines[-8:])


def converting_path(target: Path) -> Path:
    return target.with_name(f".{target.stem}.converting{target.suffix}")


def resolve_epub_member(names: Collection[str], opf_path: str, href: str) -> str | None:
    href = unquote(href.split("#", 1)[0].strip()).replace("\\", "/")
    if not href:
        return None
    member = posixpath.normpath(posixpath.join(posixpath.dirname(opf_path), href))
    return member if member in names else None


def find_opf_cover_href(opf: str) -> str | None:
    cover_id_match = re.search(
        r'name=["\']cover["\'][^>]*content=["\']([^"\']+)["\']',
        opf,
        flags=re.IGNORECASE,
    ) or re.search(
        r'content=["\']([^"\']+)["\'][^>]*name=["\']cover["\']',
        opf,
        flags=re.IGNORECASE,
    )
    if cover_id_match is None:
        return None
    cover_id = re.escape(cover_id_match.group(1))
    item_match = re.search(
        rf'id=["\']{cover_id}["\'][^>]*href=["\']([^"\']+)["\']',
        opf,
        flags=re.IGNORECASE,
    ) or re.search(
        rf'href=["\']([^"\']+)["\'][^>]*id=["\']{cover_id}["\']',
        opf,
        flags=re.IGNORECASE,
    )
    return item_match.group(1) if item_match else None


def extract_epub_cover_bytes(source: Path) -> bytes | None:
    try:
        with zipfile.ZipFile(source) as zf:
            names = zf.namelist()
            member_names = set(names)
            for opf_path in (name for name in names if name.lower().endswith(".opf")):
                href = find_opf_cover_href(zf.read(opf_path).decode("utf-8", errors="replace"))
                member = resolve_epub_member(member_names, opf_path, href) if href else None
                if member is not None:
                    return zf.read(member)

            for name in names:
                if Path(name).name.lower() in COVER_FILE_NAMES:
                    return zf.read(name)
    except (OSError, zipfile.BadZipFile, KeyError):
        return None
    return None


def sanitize_css_for_pymupdf(css: bytes) -> tuple[bytes, int]:
    output = bytearray()
    replacements = 0
    plain_start = 0
    index = 0

    def append_plain(end: int) -> None:
        nonlocal replacements
        sanitized, count = _BACKGROUND_NONE_PATTERN.subn(
            rb"background\1transparent\2",
            css[plain_start:end],
        )
        sanitized, scrolling_count = _SCROLLING_BLOCK_PATTERN.subn(
            b"",
            sanitized,
        )
        output.extend(sanitized)
        replacements += count + scrolling_count

    while index < len(css):
        if css[index : index + 2] == b"/*":
            append_plain(index)
            end = css.find(b"*/", index + 2)
            end = len(css) if end < 0 else end + 2
            output.extend(css[index:end])
            index = end
            plain_start = index
            continue

        if css[index] in (ord('"'), ord("'")):
            append_plain(index)
            quote = css[index]
            end = index + 1
            while end < len(css):
                if css[end] == ord("\\"):
                    end += 2
                    continue
                if css[end] == quote:
                    end += 1
                    break
                end += 1
            output.extend(css[index:end])
            index = end
            plain_start = index
            continue

        index += 1

    append_plain(len(css))
    return bytes(output), replacements


@contextmanager
def pymupdf_compatible_epub(source: Path, temp_dir: Path) -> Iterator[Path]:
    modified_css: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(source) as input_epub:
            for member in input_epub.infolist():
                if not member.filename.lower().endswith(".css"):
                    continue
                css = input_epub.read(member)
                sanitized, replacements = sanitize_css_for_pymupdf(css)
                if replacements:
                    modified_css[member.filename] = sanitized
    except (OSError, zipfile.BadZipFile):
        yield source
        return

    if not modified_css:
        yield source
        return

    file_descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{source.stem}.",
        suffix=".pymupdf.epub",
        dir=temp_dir,
    )
    os.close(file_descriptor)
    compatible_source = Path(temp_name)
    try:
        with (
            zipfile.ZipFile(source) as input_epub,
            zipfile.ZipFile(compatible_source, "w") as output_epub,
        ):
            output_epub.comment = input_epub.comment
            for member in input_epub.infolist():
                content = modified_css.get(member.filename)
                if content is None:
                    content = input_epub.read(member)
                output_epub.writestr(member, content)
        yield compatible_source
    finally:
        compatible_source.unlink(missing_ok=True)


def is_cover_like_page(page) -> bool:
    text = (page.get_text() or "").strip()
    if len(text) > 80:
        return False
    try:
        images = page.get_images()
    except Exception:
        images = []
    if len(images) != 1:
        return False
    try:
        blocks = page.get_text("dict").get("blocks", [])
    except Exception:
        return True
    image_blocks = [block for block in blocks if block.get("type") == 1]
    if not image_blocks:
        return True
    bbox = image_blocks[0].get("bbox")
    if not bbox or len(bbox) != 4:
        return True
    image_area = max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])
    page_area = float(page.rect.width) * float(page.rect.height)
    if page_area <= 0:
        return True
    return (image_area / page_area) >= 0.35


def insert_cover_page(output_doc, cover_bytes: bytes) -> bool:
    cover_page = output_doc.new_page(width=LETTER_WIDTH, height=LETTER_HEIGHT)
    try:
        cover_page.insert_image(cover_page.rect, stream=cover_bytes, keep_proportion=True)
    except Exception:
        output_doc.delete_page(output_doc.page_count - 1)
        return False
    return True


def convert_epub_to_pdf_with_calibre(
    source: Path,
    target: Path,
    *,
    command: list[str],
) -> tuple[str, str]:
    temp_path = converting_path(target)
    try:
        temp_path.unlink(missing_ok=True)
        try:
            result = subprocess.run(
                [*command, str(source), str(temp_path), *CALIBRE_PDF_OPTIONS],
                cwd=str(target.parent),
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=CALIBRE_CONVERT_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return "failed", f"Calibre conversion timed out after {CALIBRE_CONVERT_TIMEOUT_SECONDS}s"
        except OSError as exc:
            return "failed", f"Calibre could not be started: {exc}"
        if result.returncode != 0:
            return "failed", f"Calibre conversion failed: {command_error_tail(result)}"
        if not temp_path.exists():
            return "failed", "Calibre conversion did not create a PDF"
        os.replace(temp_path, target)
    finally:
        temp_path.unlink(missing_ok=True)
    return "converted", "EPUB converted to PDF with Calibre"


def convert_epub_to_pdf_with_pymupdf(source: Path, target: Path) -> tuple[str, str]:
    try:
        fitz = import_fitz()
    except RuntimeError as exc:
        return "failed", str(exc)

    temp_path = converting_path(target)
    try:
        temp_path.unlink(missing_ok=True)
        cover_bytes = extract_epub_cover_bytes(source)
        with suppress_pymupdf_messages(fitz):
            with pymupdf_compatible_epub(source, target.parent) as render_source:
                doc = fitz.open(render_source)
                try:
                    doc.layout(rect=fitz.Rect(0, 0, LETTER_WIDTH, LETTER_HEIGHT))
                    if doc.page_count == 0:
                        return "failed", "EPUB has no renderable pages"

                    pdf_bytes = doc.convert_to_pdf()
                finally:
                    doc.close()

            body_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            output_doc = fitz.open()
            try:
                has_cover = bool(cover_bytes) and insert_cover_page(output_doc, cover_bytes)

                start = 0
                if has_cover:
                    while start < min(body_doc.page_count, MAX_COVER_LIKE_PAGES) and is_cover_like_page(
                        body_doc[start]
                    ):
                        start += 1

                for page_number in range(start, body_doc.page_count):
                    page = output_doc.new_page(width=LETTER_WIDTH, height=LETTER_HEIGHT)
                    page.show_pdf_page(page.rect, body_doc, page_number)

                output_doc.save(temp_path, garbage=2, deflate=True)
            finally:
                body_doc.close()
                output_doc.close()

        os.replace(temp_path, target)
    except Exception as exc:
        return "failed", f"PyMuPDF conversion failed: {exc}"
    finally:
        temp_path.unlink(missing_ok=True)

    return "converted", "EPUB converted to PDF with PyMuPDF"


def convert_epub_to_pdf(
    source: Path,
    target: Path,
    *,
    overwrite: bool,
    engine: str = "pymupdf",
) -> tuple[str, str]:
    if target.exists() and not overwrite:
        return "skipped", "PDF already exists; use --overwrite to replace it"

    if engine not in {"auto", "calibre", "pymupdf"}:
        return "failed", f"Unknown conversion engine: {engine}"

    if engine == "calibre":
        command = find_calibre_command()
        if not command:
            return "failed", "Calibre ebook-convert was not found"
        return convert_epub_to_pdf_with_calibre(source, target, command=command)

    status, message = convert_epub_to_pdf_with_pymupdf(source, target)
    if engine == "pymupdf" or status != "failed":
        return status, message

    command = find_calibre_command()
    if not command:
        return status, f"{message}; Calibre ebook-convert was not found for fallback"
    calibre_status, calibre_message = convert_epub_to_pdf_with_calibre(source, target, command=command)
    return calibre_status, f"{calibre_message} (PyMuPDF failed: {message})"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=os.environ.get("BOOK_PROG"),
        description="Convert EPUB files in Inbox to PDF files.",
    )
    add_inbox_args(parser, execute_help="Create PDF files")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing PDF outputs")
    parser.add_argument(
        "--engine",
        choices=("auto", "calibre", "pymupdf"),
        default="pymupdf",
        help=(
            "Conversion engine. pymupdf is default (fast). calibre is slower, higher reflow quality. "
            "auto uses PyMuPDF and retries with Calibre when PyMuPDF fails"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_dir = Path(args.base_dir).resolve()

    try:
        inbox_dir = resolve_inbox_dir(base_dir, args.inbox_dir)
        plans = build_plan(inbox_dir, EPUB_TO_PDF, overwrite=args.overwrite, files=args.files)
    except Exception as exc:
        report_error(exc, as_json=args.json)
        return EXIT_FAILURE

    if args.execute and not confirm_execution(
        plans, "Convert these EPUB file(s) to PDF?", assume_yes=args.yes, as_json=args.json
    ):
        return EXIT_FAILURE

    try:
        if args.execute:

            def convert_one(plan: ConversionPlan) -> tuple[str, str]:
                return convert_epub_to_pdf(plan.source, plan.target, overwrite=args.overwrite, engine=args.engine)

            results = run_plan(
                plans,
                base_dir,
                convert_one,
                progress=make_progress_printer(enabled=not args.json),
                fail_fast=args.fail_fast,
                start_message=f"Converting {len(plans)} book(s) with engine={args.engine}...",
            )
        else:
            results = plan_to_results(plans, base_dir)
    except Exception as exc:
        report_error(exc, as_json=args.json)
        return EXIT_FAILURE

    return finish(results, EPUB_TO_PDF, dry_run=not args.execute, as_json=args.json)


if __name__ == "__main__":
    run_main(main)
