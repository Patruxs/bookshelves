#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from lib.book_paths import expected_display_from_file_path, parse_category_name
from lib.cli_common import EXIT_FAILURE, EXIT_OK, add_base_dir_arg, add_json_arg, json_mode, run_main
from lib.constants import CATEGORY_PATTERN, DATA_JSON
from lib.json_io import load_books
from lib.output import emit_json

LOG_FILENAME = 'library_structure.log'
CATEGORY_ROOT = '__root__'
UNNUMBERED_CATEGORY_ORDER = 999


@dataclass(frozen=True)
class ParsedBookPath:
    category: str
    topic: str
    subtopic: str
    filename: str


def parse_file_path(file_path: str) -> ParsedBookPath | None:
    category_display, _topic_display = expected_display_from_file_path(file_path)
    if category_display is None:
        return None

    parts = Path(file_path).parts
    folder_parts = parts[2:-1]
    return ParsedBookPath(
        category=parts[1],
        topic=folder_parts[0] if folder_parts else CATEGORY_ROOT,
        subtopic='/'.join(folder_parts[1:]) or CATEGORY_ROOT,
        filename=parts[-1],
    )


def load_library_books(base_dir: Path) -> list[dict]:
    if not (base_dir / DATA_JSON).is_file():
        raise FileNotFoundError(f"{DATA_JSON} not found in {base_dir}")
    return load_books(base_dir)


def write_log(content: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)


def write_log_if_changed(content: str, output_path: Path) -> bool:
    try:
        if output_path.read_text(encoding='utf-8') == content:
            return False
    except (OSError, UnicodeDecodeError):
        pass
    write_log(content, output_path)
    return True


def generate_log(base_dir: Path) -> Path:
    output_path = base_dir / LOG_FILENAME
    write_log(render_log(load_library_books(base_dir)), output_path)
    return output_path


def category_number(category_folder: str) -> int:
    match = CATEGORY_PATTERN.match(category_folder)
    return int(match.group(1)) if match else UNNUMBERED_CATEGORY_ORDER


def file_bullets(prefix: str, filenames: list[str]) -> list[str]:
    return [f"{prefix}• {filename}" for filename in sorted(filenames)]


def render_log(books: list[dict]) -> str:
    tree: dict[str, dict[str, dict[str, list[str]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for book in books:
        if not isinstance(book, dict):
            continue
        parsed = parse_file_path(str(book.get('file_path') or ''))
        if parsed:
            tree[parsed.category][parsed.topic][parsed.subtopic].append(parsed.filename)

    sorted_cats = sorted(tree, key=lambda cat: (category_number(cat), cat))

    lines = [
        "=" * 60,
        "LIBRARY STRUCTURE LOG",
        f"Generated from: {DATA_JSON} ({len(books)} books total)",
        "=" * 60,
        "",
    ]

    for cat in sorted_cats:
        match = CATEGORY_PATTERN.match(cat)
        cat_num = match.group(1) if match else '?'
        cat_book_count = sum(len(files) for topics in tree[cat].values() for files in topics.values())

        lines.append(f"[{cat_num}] {cat} ({cat_book_count} books)")
        lines.append(f"    Display Name: {parse_category_name(cat)}")

        category_root_files = tree[cat].get(CATEGORY_ROOT, {}).get(CATEGORY_ROOT, [])
        lines.extend(file_bullets("    ", category_root_files))

        sorted_topics = sorted(topic for topic in tree[cat] if topic != CATEGORY_ROOT)
        for t_idx, topic in enumerate(sorted_topics):
            is_last_topic = t_idx == len(sorted_topics) - 1
            branch = "└──" if is_last_topic else "├──"
            subtopics = tree[cat][topic]
            topic_book_count = sum(len(files) for files in subtopics.values())

            lines.append(f"    {branch} {topic} ({topic_book_count} books)")

            prefix = "        " if is_last_topic else "    │   "
            lines.extend(file_bullets(f"{prefix}    ", subtopics.get(CATEGORY_ROOT, [])))

            real_subtopics = sorted(sub for sub in subtopics if sub != CATEGORY_ROOT)
            for s_idx, sub in enumerate(real_subtopics):
                sub_branch = "└──" if s_idx == len(real_subtopics) - 1 else "├──"
                lines.append(f"{prefix}{sub_branch} {sub} ({len(subtopics[sub])} books)")
                lines.extend(file_bullets(f"{prefix}        ", subtopics[sub]))

        lines.append("")

    lines.append("=" * 60)
    lines.append("AVAILABLE CATEGORIES (for classification):")
    lines.append("")
    for cat in sorted_cats:
        if not CATEGORY_PATTERN.match(cat):
            continue
        lines.append(f"  {cat}")
        for topic in sorted(topic for topic in tree[cat] if topic != CATEGORY_ROOT):
            subtopic_names = sorted(sub for sub in tree[cat][topic] if sub != CATEGORY_ROOT)
            if subtopic_names:
                lines.extend(f"    -> {topic}/{sub}" for sub in subtopic_names)
            else:
                lines.append(f"    -> {topic}")
    lines.append("")
    numbered = [category_number(cat) for cat in sorted_cats if CATEGORY_PATTERN.match(cat)]
    lines.append(f"Next available category number: {max(numbered, default=0) + 1}")
    lines.append("=" * 60)

    return '\n'.join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Generate library_structure.log from data.json')
    add_base_dir_arg(parser)
    add_json_arg(parser)
    parser.add_argument(
        '--output', default=LOG_FILENAME,
        help=f'Output file path relative to --base-dir (default: {LOG_FILENAME})',
    )
    return parser


def write_structure_log(base_dir: Path, output_path: Path) -> tuple[int, dict]:
    try:
        books = load_library_books(base_dir)
        log_content = render_log(books)
        write_log(log_content, output_path)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_FAILURE, {"ok": False, "error": str(exc)}
    print(f"Generated {output_path} ({len(books)} books)")
    return EXIT_OK, {
        "ok": True,
        "output": output_path,
        "books": len(books),
        "bytes": len(log_content.encode("utf-8")),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_dir = args.base_dir.resolve()
    with json_mode(args.json):
        exit_code, summary = write_structure_log(base_dir, base_dir / args.output)
    if args.json:
        emit_json(summary)
    return exit_code


if __name__ == '__main__':
    run_main(main)
