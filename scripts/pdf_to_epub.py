#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import os
import uuid
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

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
from lib.output import ProgressCallback, make_progress_printer

PDF_TO_EPUB = InboxJob(
    title="My Bookshelves PDF to EPUB Converter",
    source_suffix=".pdf",
    target_suffix=".epub",
    action="Convert PDF to image-based EPUB",
    execute_hint="Add --execute to create EPUBs.",
)

JPEG_QUALITY = 85
DEFAULT_LANGUAGE = "en"


@dataclass(frozen=True)
class ImageFormat:
    pixmap_output: str
    extension: str
    media_type: str


IMAGE_FORMATS = {
    "jpeg": ImageFormat("jpeg", ".jpg", "image/jpeg"),
    "png": ImageFormat("png", ".png", "image/png"),
}

CONTAINER_XML = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/package.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""


@dataclass
class RenderedPage:
    index: int
    image_name: str
    width: int
    height: int
    image_bytes: bytes


@dataclass(frozen=True)
class PageEntry:
    index: int
    image_name: str
    width: int
    height: int


def import_fitz():
    fitz = import_pymupdf()
    if fitz is None:
        raise RuntimeError(
            "PyMuPDF is required. Install dependencies with: "
            "python -m pip install -r requirements.txt"
        )
    return fitz


def should_report_page(current: int, total: int) -> bool:
    if total <= 0:
        return False
    if current == 1 or current == total:
        return True
    step = max(1, total // 10)
    return current % step == 0


def render_pdf_pages(
    source: Path,
    *,
    zoom: float,
    image_format: ImageFormat = IMAGE_FORMATS["jpeg"],
    on_page: Callable[[int, int], None] | None = None,
) -> Iterator[RenderedPage]:
    fitz = import_fitz()
    doc = fitz.open(source)
    try:
        if doc.needs_pass:
            raise RuntimeError("PDF is password-protected; unlock it before converting")
        if doc.page_count == 0:
            raise RuntimeError("PDF has no renderable pages")

        total_pages = doc.page_count
        matrix = fitz.Matrix(zoom, zoom)
        for index, page in enumerate(doc, 1):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            yield RenderedPage(
                index=index,
                image_name=f"page_{index:04d}{image_format.extension}",
                width=pix.width,
                height=pix.height,
                image_bytes=pix.tobytes(image_format.pixmap_output, jpg_quality=JPEG_QUALITY),
            )
            if on_page is not None:
                on_page(index, total_pages)
    finally:
        doc.close()


def page_xhtml(page: PageEntry, title: str, language: str) -> str:
    escaped_title = html.escape(title)
    alt = html.escape(f"{title} page {page.index}")
    lang = html.escape(language)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="{lang}" xml:lang="{lang}">
<head>
  <title>{escaped_title} - Page {page.index}</title>
  <link rel="stylesheet" type="text/css" href="../styles/style.css"/>
</head>
<body>
  <main>
    <img src="../images/{page.image_name}" alt="{alt}" width="{page.width}" height="{page.height}"/>
  </main>
</body>
</html>
"""


def package_opf(
    title: str,
    identifier: str,
    modified: str,
    language: str,
    pages: list[PageEntry],
    image_format: ImageFormat,
) -> str:
    escaped_title = html.escape(title)
    image_items = "\n".join(
        f'    <item id="img-{page.index}" href="images/{page.image_name}" media-type="{image_format.media_type}"/>'
        for page in pages
    )
    page_items = "\n".join(
        f'    <item id="page-{page.index}" href="pages/page_{page.index:04d}.xhtml" media-type="application/xhtml+xml"/>'
        for page in pages
    )
    spine_items = "\n".join(f'    <itemref idref="page-{page.index}"/>' for page in pages)

    return f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">{identifier}</dc:identifier>
    <dc:title>{escaped_title}</dc:title>
    <dc:language>{html.escape(language)}</dc:language>
    <meta property="dcterms:modified">{modified}</meta>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="style" href="styles/style.css" media-type="text/css"/>
{page_items}
{image_items}
  </manifest>
  <spine>
{spine_items}
  </spine>
</package>
"""


def nav_xhtml(title: str, language: str, pages: list[PageEntry]) -> str:
    escaped_title = html.escape(title)
    lang = html.escape(language)
    links = "\n".join(
        f'      <li><a href="pages/page_{page.index:04d}.xhtml">Page {page.index}</a></li>'
        for page in pages
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{lang}" xml:lang="{lang}">
<head>
  <title>{escaped_title}</title>
</head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>{escaped_title}</h1>
    <ol>
{links}
    </ol>
  </nav>
</body>
</html>
"""


def stylesheet() -> str:
    return """html, body {
  margin: 0;
  padding: 0;
  background: #ffffff;
}

main {
  margin: 0;
  padding: 0;
  text-align: center;
}

img {
  display: block;
  width: 100%;
  height: auto;
  margin: 0 auto;
}
"""


def write_epub(
    target: Path,
    title: str,
    rendered_pages: Iterator[RenderedPage],
    *,
    language: str,
    image_format: ImageFormat,
) -> None:
    identifier = f"urn:uuid:{uuid.uuid4()}"
    modified = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    pages: list[PageEntry] = []
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as epub:
        epub.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        epub.writestr("META-INF/container.xml", CONTAINER_XML)
        epub.writestr("OEBPS/styles/style.css", stylesheet())
        for rendered in rendered_pages:
            page = PageEntry(rendered.index, rendered.image_name, rendered.width, rendered.height)
            epub.writestr(
                f"OEBPS/images/{page.image_name}",
                rendered.image_bytes,
                compress_type=zipfile.ZIP_STORED,
            )
            epub.writestr(f"OEBPS/pages/page_{page.index:04d}.xhtml", page_xhtml(page, title, language))
            pages.append(page)
        epub.writestr("OEBPS/package.opf", package_opf(title, identifier, modified, language, pages, image_format))
        epub.writestr("OEBPS/nav.xhtml", nav_xhtml(title, language, pages))


def convert_pdf_to_epub(
    source: Path,
    target: Path,
    *,
    overwrite: bool,
    zoom: float,
    image_format: str = "jpeg",
    language: str = DEFAULT_LANGUAGE,
    on_page: Callable[[int, int], None] | None = None,
) -> tuple[str, str]:
    if target.exists() and not overwrite:
        return "skipped", "EPUB already exists; use --overwrite to replace it"
    if zoom <= 0:
        return "failed", "--zoom must be greater than 0"

    temp_path = target.with_name(f".{target.stem}.converting{target.suffix}")
    try:
        temp_path.unlink(missing_ok=True)
        selected_format = IMAGE_FORMATS[image_format]
        pages = render_pdf_pages(source, zoom=zoom, image_format=selected_format, on_page=on_page)
        write_epub(temp_path, source.stem, pages, language=language, image_format=selected_format)
        os.replace(temp_path, target)
    except Exception as exc:
        return "failed", f"Conversion failed: {exc}"
    finally:
        temp_path.unlink(missing_ok=True)

    return "converted", "PDF converted to image-based EPUB"


def page_progress(progress: ProgressCallback | None) -> Callable[[int, int], None] | None:
    if progress is None:
        return None

    def on_page(current: int, total_pages: int) -> None:
        if should_report_page(current, total_pages):
            progress(f"  page {current}/{total_pages}")

    return on_page


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=os.environ.get("BOOK_PROG"),
        description="Convert PDF files in Inbox to image-based EPUB files.",
    )
    add_inbox_args(parser, execute_help="Create EPUB files")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing EPUB outputs")
    parser.add_argument("--zoom", type=float, default=1.5, help="PDF render zoom for page images")
    parser.add_argument(
        "--image-format",
        choices=tuple(IMAGE_FORMATS),
        default="jpeg",
        help=f"Page image format (default: jpeg, quality {JPEG_QUALITY})",
    )
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help="EPUB dc:language code (default: en)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_dir = Path(args.base_dir).resolve()

    try:
        inbox_dir = resolve_inbox_dir(base_dir, args.inbox_dir)
        plans = build_plan(inbox_dir, PDF_TO_EPUB, overwrite=args.overwrite, files=args.files)
    except Exception as exc:
        report_error(exc, as_json=args.json)
        return EXIT_FAILURE

    if args.execute and not confirm_execution(
        plans, "Convert these PDF file(s) to EPUB?", assume_yes=args.yes, as_json=args.json
    ):
        return EXIT_FAILURE

    try:
        if args.execute:
            progress = make_progress_printer(enabled=not args.json)

            def convert_one(plan: ConversionPlan) -> tuple[str, str]:
                return convert_pdf_to_epub(
                    plan.source,
                    plan.target,
                    overwrite=args.overwrite,
                    zoom=args.zoom,
                    image_format=args.image_format,
                    language=args.language,
                    on_page=page_progress(progress),
                )

            results = run_plan(plans, base_dir, convert_one, progress=progress, fail_fast=args.fail_fast)
        else:
            results = plan_to_results(plans, base_dir)
    except Exception as exc:
        report_error(exc, as_json=args.json)
        return EXIT_FAILURE

    return finish(results, PDF_TO_EPUB, dry_run=not args.execute, as_json=args.json)


if __name__ == "__main__":
    run_main(main)
