from __future__ import annotations

import asyncio
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult, SuspendNotSupported
from textual.message import Message
from textual.widget import Widget
from textual.widgets import RichLog, Static

import cli
from bookshelves_tui.modals import ConfirmModal

if TYPE_CHECKING:
    from bookshelves_tui.app import BookshelvesApp

SCRIPTS_DIR = Path(cli.__file__).resolve().parent
NOT_RUN = -1
STREAM_LINE_LIMIT = 1024 * 1024
PERFORM_ARGS = ["--execute", "--yes"]


def build_argv(command: str, args: list[str]) -> list[str]:
    spec = cli.COMMANDS[command]
    return [sys.executable, str(SCRIPTS_DIR / spec["script"]), *spec["inject_args"], *args]


def display_args(args: list[str]) -> list[str]:
    shown: list[str] = []
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
        elif arg == "--base-dir":
            skip_next = True
        else:
            shown.append(arg)
    return shown


def subprocess_env() -> dict[str, str]:
    return {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}


class CommandFinished(Message):
    def __init__(self, command: str, args: list[str], exit_code: int) -> None:
        super().__init__()
        self.command = command
        self.args = args
        self.exit_code = exit_code


class StatusBar(Static):
    def on_mount(self) -> None:
        self.show_idle()

    def show_idle(self) -> None:
        self.show("Idle", "")

    def show_running(self, command: str, args: list[str]) -> None:
        self.show(f"Running: {shlex.join([command, *display_args(args)])}", "-running")

    def show_exit(self, exit_code: int) -> None:
        if exit_code == 0:
            self.show("Done (exit 0)", "-done")
        else:
            self.show(f"Failed (exit {exit_code})", "-failed")

    def show(self, text: str, state_class: str) -> None:
        self.update(text)
        for candidate in ("-running", "-done", "-failed"):
            self.set_class(candidate == state_class, candidate)


class OutputPane(Widget):
    def compose(self) -> ComposeResult:
        yield RichLog(id="output-log", markup=False, highlight=False, wrap=True, max_lines=5000)

    def on_mount(self) -> None:
        self.border_title = "Output"

    @property
    def log_view(self) -> RichLog:
        return self.query_one("#output-log", RichLog)

    def write_command(self, argv: list[str]) -> None:
        self.log_view.write(Text(f"▸ {shlex.join(argv)}", style="bold cyan"))

    def write_line(self, line: str) -> None:
        self.log_view.write(Text.from_ansi(line))

    def write_exit(self, exit_code: int) -> None:
        if exit_code == 0:
            self.log_view.write(Text("✔ exit 0", style="bold green"))
        else:
            self.log_view.write(Text(f"✖ exit {exit_code}", style="bold red"))

    def clear(self) -> None:
        self.log_view.clear()


class CommandRunner:
    def __init__(self, app: BookshelvesApp, base_dir: Path) -> None:
        self.app = app
        self.base_dir = base_dir
        self.busy = False

    @property
    def base_dir_args(self) -> list[str]:
        return ["--base-dir", str(self.base_dir)]

    @property
    def output(self) -> OutputPane:
        return self.app.query_one(OutputPane)

    @property
    def status_bar(self) -> StatusBar:
        return self.app.query_one(StatusBar)

    def start(self, command: str, args: list[str]) -> list[str]:
        argv = build_argv(command, args)
        self.output.write_command(argv)
        self.status_bar.show_running(command, args)
        return argv

    def claim(self) -> bool:
        if self.busy:
            self.app.notify("A command is already running.", severity="warning")
            return False
        self.busy = True
        return True

    def finish(self, command: str, args: list[str], exit_code: int) -> None:
        self.busy = False
        self.output.write_exit(exit_code)
        self.status_bar.show_exit(exit_code)
        self.app.post_message(CommandFinished(command, args, exit_code))

    async def run(self, command: str, args: list[str]) -> int:
        if not self.claim():
            return NOT_RUN
        argv = self.start(command, args)
        exit_code = NOT_RUN
        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(self.base_dir),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=subprocess_env(),
                limit=STREAM_LINE_LIMIT,
            )
        except OSError as exc:
            self.output.write_line(str(exc))
            self.finish(command, args, exit_code)
            return exit_code
        try:
            assert process.stdout is not None
            async for raw_line in process.stdout:
                self.output.write_line(raw_line.decode("utf-8", errors="replace").rstrip("\r\n"))
            exit_code = await process.wait()
        except asyncio.CancelledError:
            if process.returncode is None:
                process.kill()
            raise
        finally:
            self.finish(command, args, exit_code)
        return exit_code

    def run_interactive(self, command: str, args: list[str]) -> int:
        if not self.claim():
            return NOT_RUN
        argv = self.start(command, args)
        exit_code = NOT_RUN
        try:
            with self.app.suspend():
                exit_code = subprocess.run(argv, cwd=str(self.base_dir)).returncode
        except (SuspendNotSupported, OSError) as exc:
            self.app.notify(f"Cannot run {command}: {exc}", severity="error")
        finally:
            self.finish(command, args, exit_code)
        return exit_code

    async def preview_then_execute(self, command: str, args: list[str], question: str,
                                   checkbox: str | None = None,
                                   checked_args: list[str] | None = None,
                                   danger: bool = False) -> int | None:
        if self.busy:
            self.app.notify("A command is already running.", severity="warning")
            return None
        dry_run_exit_code = await self.run(command, args)
        if dry_run_exit_code != 0:
            self.app.notify(f"Dry run failed (exit {dry_run_exit_code}); nothing was executed.", severity="error")
            return None
        result = await self.app.push_screen_wait(ConfirmModal(question, danger=danger, checkbox=checkbox))
        if not result.ok:
            return None
        final_args = [*args, *PERFORM_ARGS]
        if result.checked and checked_args:
            final_args.extend(checked_args)
        return await self.run(command, final_args)
