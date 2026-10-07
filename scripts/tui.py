#!/usr/bin/env python3
import sys

USAGE = """My Bookshelves TUI

Usage:
  python scripts/tui.py
  book tui
  bookshelves

Opens a full-screen terminal app; press ? inside it for keyboard shortcuts.
For scripted use run `book <command>` (see `book --help`)."""


def main() -> int:
    if any(arg in ("-h", "--help", "help") for arg in sys.argv[1:]):
        print(USAGE)
        return 0
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print(USAGE)
        return 2
    from bookshelves_tui.app import main as run_app
    run_app()
    return 0


if __name__ == "__main__":
    sys.exit(main())
