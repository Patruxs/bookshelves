from __future__ import annotations

import argparse
import importlib
import json
import os
import shlex
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from typing import TextIO

from .output import configure_utf8_stdio

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
SCRIPTS_DIR: Path = REPO_ROOT / "scripts"

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
INTERRUPTED_EXIT_CODE = 130

AFFIRMATIVE_ANSWERS = {"y", "yes"}
MODE_FLAGS = {"--dry-run", "--execute"}


class ConfirmationRequired(Exception):
    pass


def add_base_dir_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=REPO_ROOT,
        help="Project root directory (default: repo root)",
    )


def add_json_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON on stdout")


def add_mode_args(
    parser: argparse.ArgumentParser,
    *,
    execute_help: str = "Apply the changes (default is a dry run)",
) -> None:
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview changes without touching files (default)")
    mode.add_argument("--execute", action="store_true", help=execute_help)
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")


def confirm(question: str, *, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        raise ConfirmationRequired("confirmation required; pass --yes")
    try:
        answer = input(f"{question} [y/N] ")
    except EOFError:
        return False
    return answer.strip().lower() in AFFIRMATIVE_ANSWERS


@contextmanager
def json_mode(enabled: bool) -> Iterator[TextIO]:
    original_stdout = sys.stdout
    if not enabled:
        yield original_stdout
        return
    with redirect_stdout(sys.stderr):
        yield original_stdout


def execute_command(command: str, argv: list[str]) -> str:
    kept_args = [arg for arg in argv if arg not in MODE_FLAGS]
    return shlex.join(["./book", command, *kept_args, "--execute"])


def refresh_structure_log(base_dir: Path) -> bool:
    try:
        if str(SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_DIR))
        structure_log = importlib.import_module("generate_structure_log")
        structure_log.generate_log(Path(base_dir))
    except Exception:
        return False
    return True


def report_confirmation_required(error: ConfirmationRequired, argv: list[str]) -> None:
    if "--json" in argv:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False, indent=2))
    else:
        print(f"ERROR: {error}", file=sys.stderr)


def silence_broken_stdout() -> None:
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, sys.stdout.fileno())


def run_main(main: Callable[[list[str] | None], int]) -> None:
    configure_utf8_stdio()
    argv = sys.argv[1:]
    try:
        exit_code = main(argv)
        sys.stdout.flush()
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        exit_code = INTERRUPTED_EXIT_CODE
    except ConfirmationRequired as error:
        report_confirmation_required(error, argv)
        exit_code = EXIT_USAGE
    except BrokenPipeError:
        silence_broken_stdout()
        exit_code = EXIT_FAILURE
    sys.exit(EXIT_OK if exit_code is None else exit_code)
