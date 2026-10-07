#!/usr/bin/env python3
import difflib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TypedDict

from lib.cli_common import EXIT_FAILURE, EXIT_OK, EXIT_USAGE, INTERRUPTED_EXIT_CODE, run_main

SCRIPTS_DIR = Path(__file__).parent
HELP_FLAGS = {"-h", "--help"}
PROG_ENV_VAR = "BOOK_PROG"


class CommandSpec(TypedDict):
    script: str
    inject_args: list[str]
    desc: str
    examples: list[str]


COMMANDS: dict[str, CommandSpec] = {
    "list": {
        "script": "delete_books.py",
        "inject_args": ["--list"],
        "desc": "List all books, topics, and categories",
        "examples": ["list"],
    },
    "delete": {
        "script": "delete_books.py",
        "inject_args": [],
        "desc": "Delete books, topics, or categories",
        "examples": [
            'delete --book "Title"',
            'delete --book "Title" --execute',
            'delete --topic "Topic" --category "Cat" --execute',
            'delete --category "Cat" --execute',
        ],
    },
    "doctor": {
        "script": "doctor.py",
        "inject_args": [],
        "desc": "Validate repo health and dependencies",
        "examples": ["doctor", "doctor --strict", "doctor --json"],
    },
    "smoke": {
        "script": "smoke_site.py",
        "inject_args": [],
        "desc": "Smoke check static site contracts",
        "examples": [
            "smoke",
            "smoke --check-download-urls",
            "smoke --allow-missing-download-url",
        ],
    },
    "unlock-pdfs": {
        "script": "unlock_pdfs.py",
        "inject_args": [],
        "desc": "Remove password encryption from PDFs in Inbox",
        "examples": ["unlock-pdfs", "unlock-pdfs --execute"],
    },
    "epub-to-pdf": {
        "script": "epub_to_pdf.py",
        "inject_args": [],
        "desc": "Convert EPUB files in Inbox to PDF",
        "examples": [
            "epub-to-pdf",
            "epub-to-pdf --execute",
            'epub-to-pdf --execute --file "Book Name"',
        ],
    },
    "pdf-to-epub": {
        "script": "pdf_to_epub.py",
        "inject_args": [],
        "desc": "Convert PDF files in Inbox to image-based EPUB",
        "examples": ["pdf-to-epub", "pdf-to-epub --execute"],
    },
    "update": {
        "script": "update_books.py",
        "inject_args": [],
        "desc": "Update book metadata, rename topics/categories",
        "examples": [
            'update --book "Title" --set-description "Desc" --execute',
            'update --book "Title" --set-category "Cat" --execute',
            'update --book "Title" --set-topic "Topic" --execute',
            'update --topic "Old" --category "Cat" --rename "New" --execute',
            'update --category "Old" --rename "New" --execute',
        ],
    },
    "generate": {
        "script": "generate_data.py",
        "inject_args": [],
        "desc": "Generate data.json and cover images from Books/",
        "examples": ["generate"],
    },
    "rename": {
        "script": "rename_books.py",
        "inject_args": [],
        "desc": "Normalize book filenames to ASCII Snake_Case",
        "examples": ["rename", "rename --execute"],
    },
    "upload": {
        "script": "upload_releases.py",
        "inject_args": [],
        "desc": "Upload books to GitHub Releases",
        "examples": ["upload --dry-run", "upload --execute"],
    },
    "structure": {
        "script": "generate_structure_log.py",
        "inject_args": [],
        "desc": "Regenerate library_structure.log",
        "examples": ["structure"],
    },
    "auto-organize": {
        "script": "auto_organize.py",
        "inject_args": [],
        "desc": "Launch an AI agent to classify Inbox books",
        "examples": [
            "auto-organize",
            "auto-organize --agent claude",
            "auto-organize --print-prompt",
            "auto-organize --print-command",
            "auto-organize --list-agents --json",
        ],
    },
    "apply-plan": {
        "script": "apply_plan.py",
        "inject_args": [],
        "desc": "Apply an Inbox classification plan: move, generate, describe, validate",
        "examples": ["apply-plan plan.json", "apply-plan plan.json --execute --json"],
    },
    "reset": {
        "script": "reset_library.py",
        "inject_args": [],
        "desc": "Move current metadata and covers to .backups/ (fresh start)",
        "examples": ["reset", "reset --execute"],
    },
    "tui": {
        "script": "tui.py",
        "inject_args": [],
        "desc": "Open the interactive terminal UI",
        "examples": ["tui"],
    },
}

ALIASES = {
    "validate": "doctor",
    "docter": "doctor",
    "doc": "doctor",
    "check": "doctor",
    "unlock": "unlock-pdfs",
    "unlock-pdf": "unlock-pdfs",
    "pdf-unlock": "unlock-pdfs",
    "epub2pdf": "epub-to-pdf",
    "epubtopdf": "epub-to-pdf",
    "epub-pdf": "epub-to-pdf",
    "convert-epub": "epub-to-pdf",
    "convert-epubs": "epub-to-pdf",
    "pdf2epub": "pdf-to-epub",
    "pdftoepub": "pdf-to-epub",
    "pdf-epub": "pdf-to-epub",
    "convert-pdf": "pdf-to-epub",
    "convert-pdfs": "pdf-to-epub",
    "organize": "auto-organize",
}

SIGNAL_EXIT_BASE = 128


def aliases_for(command: str) -> list[str]:
    return [alias for alias, target in ALIASES.items() if target == command]


def build_help() -> str:
    lines = [
        "=" * 60,
        "📚 My Bookshelves CLI",
        "=" * 60,
        "",
        "Usage: book <command> [options]",
        "       book help <command>",
        "       book --help --json",
        "",
        "Commands:",
    ]
    for name, spec in COMMANDS.items():
        lines.append(f"  {name:<14} {spec['desc']}")
        aliases = aliases_for(name)
        if aliases:
            lines.append(f"  {'':<14} aliases: {', '.join(aliases)}")
    lines += ["", "Examples:"]
    for spec in COMMANDS.values():
        lines += [f"  book {example}" for example in spec["examples"]]
    lines.append("")
    return "\n".join(lines)


def commands_as_json() -> list[dict[str, object]]:
    return [
        {"name": name, "desc": spec["desc"], "aliases": aliases_for(name), "examples": spec["examples"]}
        for name, spec in COMMANDS.items()
    ]


def print_help(*, as_json: bool) -> None:
    if as_json:
        print(json.dumps(commands_as_json(), ensure_ascii=False, indent=2))
    else:
        print(build_help())


def build_command_footer(command: str) -> str:
    spec = COMMANDS[command]
    lines = ["", "Examples:", *(f"  book {example}" for example in spec["examples"])]
    aliases = aliases_for(command)
    if aliases:
        lines += ["", f"Aliases: {', '.join(aliases)}"]
    return "\n".join(lines)


def normalize_command(command: str) -> str:
    return ALIASES.get(command, command)


def suggest_commands(command: str) -> list[str]:
    known_names = [*COMMANDS, *ALIASES]
    matches = difflib.get_close_matches(command, known_names, n=3, cutoff=0.6)
    return list(dict.fromkeys(normalize_command(match) for match in matches))


def report_unknown_command(command: str) -> None:
    print(f"❌ Unknown command: \"{command}\"", file=sys.stderr)
    suggestions = suggest_commands(command)
    if suggestions:
        print(f"   Did you mean: {', '.join(suggestions)}?", file=sys.stderr)
    print(f"   Available: {', '.join(COMMANDS)}", file=sys.stderr)
    print("   Run: book --help", file=sys.stderr)


def exit_code_from_returncode(returncode: int) -> int:
    if returncode < 0:
        return SIGNAL_EXIT_BASE - returncode
    return returncode


def run_command(command: str, args: list[str]) -> int:
    spec = COMMANDS[command]
    script_path = SCRIPTS_DIR / spec["script"]
    if not script_path.exists():
        print(f"❌ Script not found: {script_path}", file=sys.stderr)
        return EXIT_FAILURE

    cmd = [sys.executable, str(script_path), *spec["inject_args"], *args]
    env = {**os.environ, PROG_ENV_VAR: f"book {command}"}
    try:
        result = subprocess.run(cmd, env=env)
    except KeyboardInterrupt:
        return INTERRUPTED_EXIT_CODE
    return exit_code_from_returncode(result.returncode)


def show_command_help(command: str) -> int:
    sys.stdout.flush()
    exit_code = run_command(command, ["--help"])
    print(build_command_footer(command))
    return exit_code


def resolve_command(requested: str) -> str | None:
    command = normalize_command(requested)
    if command not in COMMANDS:
        report_unknown_command(requested)
        return None
    return command


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in HELP_FLAGS:
        print_help(as_json="--json" in argv)
        return EXIT_OK

    if argv[0] == "help":
        if len(argv) < 2:
            print_help(as_json=False)
            return EXIT_OK
        command = resolve_command(argv[1])
        return EXIT_USAGE if command is None else show_command_help(command)

    command = resolve_command(argv[0])
    if command is None:
        return EXIT_USAGE

    extra_args = argv[1:]
    if HELP_FLAGS.intersection(extra_args) and "--json" not in extra_args:
        return show_command_help(command)
    return run_command(command, extra_args)


if __name__ == "__main__":
    run_main(main)
