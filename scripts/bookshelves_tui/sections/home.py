from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.widgets import Button, DataTable, Label, Static

from bookshelves_tui import flows
from bookshelves_tui.context import SectionWidget
from bookshelves_tui.library import list_inbox_files
from lib.book_paths import format_size
from lib.constants import BOOKS_DIR, DATA_JSON, INBOX_DIR
from lib.json_io import load_books

if TYPE_CHECKING:
    from bookshelves_tui.app import BookshelvesApp

Flow = Callable[["BookshelvesApp"], Awaitable[int | None]]
EMPTY_INBOX_TEXT = f"Drop .pdf, .epub or .docx files into {INBOX_DIR}/, then press a to Auto-Organize them."
COMMIT_HINT = "git add / commit / push in your shell"


@dataclass(frozen=True)
class StepAction:
    key: str
    label: str
    flow: Flow

    @property
    def button_id(self) -> str:
        return f"home-run-{self.flow.__name__}"


@dataclass(frozen=True)
class Step:
    step_id: str
    title: str
    actions: tuple[StepAction, ...]


@dataclass(frozen=True)
class StepStatus:
    text: str
    ok: bool


STEPS = (
    Step("inbox", "Inbox", (
        StepAction("a", "Auto-Organize", flows.run_auto_organize),
        StepAction("u", "Unlock PDFs", flows.run_unlock_pdfs),
        StepAction("p", "EPUB→PDF", flows.run_epub_to_pdf),
        StepAction("b", "PDF→EPUB", flows.run_pdf_to_epub),
        StepAction("n", "Rename", flows.run_rename_files),
    )),
    Step("generate", "Generate", (StepAction("g", "Generate", flows.run_generate),)),
    Step("doctor", "Doctor", (StepAction("d", "Doctor", flows.run_doctor),)),
    Step("upload", "Upload", (StepAction("U", "Upload new books", flows.run_upload_new_books),)),
    Step("commit", "Commit", ()),
)
FLOWS_BY_BUTTON = {action.button_id: action.flow for step in STEPS for action in step.actions}


def newest_mtime_under(directory: Path) -> float:
    newest = directory.stat().st_mtime
    for path in directory.rglob("*"):
        if not any(part.startswith(".") for part in path.relative_to(directory).parts):
            newest = max(newest, path.stat().st_mtime)
    return newest


def inbox_status(inbox_file_count: int) -> StepStatus:
    if inbox_file_count:
        return StepStatus(f"{inbox_file_count} files waiting", ok=False)
    return StepStatus("empty", ok=True)


def generate_status(base_dir: Path) -> StepStatus:
    data_path = base_dir / DATA_JSON
    if not data_path.is_file():
        return StepStatus(f"{Path(DATA_JSON).name} missing", ok=False)
    books_dir = base_dir / BOOKS_DIR
    if books_dir.is_dir() and newest_mtime_under(books_dir) > data_path.stat().st_mtime:
        return StepStatus(f"{BOOKS_DIR}/ changed since last generate", ok=False)
    return StepStatus("up to date", ok=True)


def doctor_status(report: flows.DoctorReport | None) -> StepStatus:
    if report is None:
        return StepStatus("not run yet", ok=False)
    return StepStatus(f"{report.status} · {report.errors} errors · {report.warnings} warnings", ok=not report.failed)


def upload_status(base_dir: Path) -> StepStatus:
    try:
        books = load_books(base_dir)
    except (OSError, ValueError):
        return StepStatus(f"cannot read {DATA_JSON}", ok=False)
    not_uploaded = sum(1 for book in books if not book.get("download_url"))
    if not_uploaded:
        return StepStatus(f"{not_uploaded} books not uploaded", ok=False)
    return StepStatus("all uploaded", ok=True)


class StepPanel(Vertical):
    def __init__(self, number: int, step: Step) -> None:
        super().__init__(id=f"step-{step.step_id}", classes="home-step")
        self.number = number
        self.step = step

    def compose(self) -> ComposeResult:
        with Horizontal(classes="step-heading"):
            yield Label(f"{self.number} {self.step.title}", classes="step-title")
            yield Label("", classes="step-status")
        if self.step.step_id == "inbox":
            yield DataTable(id="inbox-table", cursor_type="none", zebra_stripes=True)
            yield Static(EMPTY_INBOX_TEXT, id="inbox-empty", classes="step-hint")
        if self.step.step_id == "commit":
            yield Static(COMMIT_HINT, classes="step-hint")
        if self.step.actions:
            with Horizontal(classes="step-actions"):
                for action in self.step.actions:
                    yield Button(Content(f"{action.label} [{action.key}]"), id=action.button_id, compact=True)

    def show_status(self, status: StepStatus) -> None:
        label = self.query_one(".step-status", Label)
        label.update(Text(f"{'✔' if status.ok else '●'} {status.text}"))
        label.set_class(status.ok, "-ok")
        label.set_class(not status.ok, "-pending")


class HomeSection(SectionWidget, can_focus=True):
    BINDINGS = [
        Binding("up", "move_step(-1)", "Previous step", show=False),
        Binding("down", "move_step(1)", "Next step", show=False),
        Binding("enter", "run_highlighted", "Run step"),
        *(Binding(action.key, f"run_flow('{action.button_id}')", action.label, show=False)
          for step in STEPS for action in step.actions),
    ]

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self.highlighted = 0

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="home-steps", can_focus=False):
            for number, step in enumerate(STEPS, start=1):
                yield StepPanel(number, step)

    def on_mount(self) -> None:
        table = self.query_one("#inbox-table", DataTable)
        table.can_focus = False
        table.add_columns("File", "Type", Text("Size", justify="right"))
        for button in self.query(Button):
            button.can_focus = False
        self.highlight(0)
        self.reload()

    def on_show(self) -> None:
        self.reload()

    @property
    def base_dir(self) -> Path:
        return self.bookshelves_app.base_dir

    @property
    def panels(self) -> list[StepPanel]:
        return list(self.query(StepPanel))

    def reload(self) -> None:
        inbox_count = self.reload_inbox_table()
        statuses = {
            "inbox": inbox_status(inbox_count),
            "generate": generate_status(self.base_dir),
            "doctor": doctor_status(self.bookshelves_app.last_doctor_report),
            "upload": upload_status(self.base_dir),
        }
        for panel in self.panels:
            status = statuses.get(panel.step.step_id)
            if status is not None:
                panel.show_status(status)

    def reload_inbox_table(self) -> int:
        inbox_dir = self.base_dir / INBOX_DIR
        inbox_files = list_inbox_files(self.base_dir)
        table = self.query_one("#inbox-table", DataTable)
        table.clear()
        for path in inbox_files:
            relative_path = path.relative_to(inbox_dir).as_posix()
            table.add_row(
                relative_path,
                path.suffix.lstrip(".").lower() or "—",
                Text(format_size(path.stat().st_size), justify="right"),
                key=relative_path,
            )
        table.display = bool(inbox_files)
        self.query_one("#inbox-empty", Static).display = not inbox_files
        return len(inbox_files)

    def highlight(self, index: int) -> None:
        panels = self.panels
        self.highlighted = max(0, min(index, len(panels) - 1))
        for position, panel in enumerate(panels):
            panel.set_class(position == self.highlighted, "-highlighted")
        panels[self.highlighted].scroll_visible()

    def action_move_step(self, delta: int) -> None:
        self.highlight(self.highlighted + delta)

    def action_run_highlighted(self) -> None:
        step = STEPS[self.highlighted]
        if not step.actions:
            self.notify(COMMIT_HINT)
            return
        self.action_run_flow(step.actions[0].button_id)

    @on(Button.Pressed, ".step-actions Button")
    def run_pressed_button(self, event: Button.Pressed) -> None:
        self.action_run_flow(event.button.id or "")

    def action_run_flow(self, button_id: str) -> None:
        self.highlight(next(index for index, step in enumerate(STEPS)
                            if any(action.button_id == button_id for action in step.actions)))
        self.run_flow(FLOWS_BY_BUTTON[button_id])

    @work(group="home")
    async def run_flow(self, flow: Flow) -> None:
        await flow(self.bookshelves_app)
