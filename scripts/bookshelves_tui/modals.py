from __future__ import annotations

from dataclasses import dataclass

from rich.table import Table
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, OptionList, Static, TextArea
from textual.widgets.option_list import Option

NEW_OPTION_ID = "__new__"

HELP_SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    ("Global", [
        ("1-3", "Jump to Home, Library, Tools"),
        ("Tab / Shift+Tab", "Cycle focus between content and output"),
        ("o", "Output pane: default / maximised / hidden"),
        ("Ctrl+L", "Clear output"),
        ("?", "This help"),
        ("q", "Quit"),
        ("Esc", "Back / close"),
    ]),
    ("Home", [
        ("Up / Down", "Move between the publish steps: Inbox, Generate, Doctor, Upload, Commit"),
        ("Enter", "Run the highlighted step's first button"),
        ("a", "Auto-Organize Inbox/ with an AI agent"),
        ("u", "Unlock PDFs"),
        ("p", "EPUB → PDF"),
        ("b", "PDF → EPUB"),
        ("n", "Rename files"),
        ("g", "Generate data.json and covers"),
        ("d", "Doctor"),
        ("U", "Upload new books (dry run, then confirm)"),
    ]),
    ("Library", [
        ("Up / Down", "Move in the tree; Enter expands a category or topic"),
        ("/", "Filter the tree, Esc clears"),
        ("e", "Edit book description"),
        ("m", "Move book to another category / topic"),
        ("r", "Rename topic or category"),
        ("d", "Delete book, topic or category"),
        ("", "The buttons under the tree run the same actions"),
    ]),
    ("Tools", [
        ("Up / Down", "Move through the Checks, Generate and Danger groups"),
        ("Enter", "Run the highlighted row"),
        ("", "Danger rows dry-run first, then need YES typed to proceed"),
    ]),
]


@dataclass(frozen=True)
class ConfirmResult:
    ok: bool
    checked: bool = False


class ConfirmModal(ModalScreen[ConfirmResult]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, question: str, danger: bool = False, checkbox: str | None = None,
                 require_typed: str | None = None) -> None:
        super().__init__(classes="modal")
        self.question = question
        self.danger = danger
        self.checkbox_label = checkbox
        self.require_typed = require_typed

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog" + (" -danger" if self.danger else "")):
            yield Label(self.question, classes="modal-title")
            if self.checkbox_label is not None:
                yield Checkbox(self.checkbox_label, id="confirm-checkbox")
            if self.require_typed is not None:
                yield Label(f"Type {self.require_typed!r} to confirm", classes="modal-hint")
                yield Input(placeholder=self.require_typed, id="confirm-typed")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Confirm", id="confirm", variant="error" if self.danger else "primary",
                             disabled=self.require_typed is not None)

    def on_mount(self) -> None:
        if self.require_typed is not None:
            self.query_one("#confirm-typed", Input).focus()
        elif self.danger:
            self.query_one("#cancel", Button).focus()
        else:
            self.query_one("#confirm", Button).focus()

    def typed_matches(self) -> bool:
        if self.require_typed is None:
            return True
        return self.query_one("#confirm-typed", Input).value.strip() == self.require_typed

    def checkbox_checked(self) -> bool:
        if self.checkbox_label is None:
            return False
        return self.query_one("#confirm-checkbox", Checkbox).value

    @on(Input.Changed, "#confirm-typed")
    def update_confirm_button(self) -> None:
        self.query_one("#confirm", Button).disabled = not self.typed_matches()

    @on(Input.Submitted, "#confirm-typed")
    @on(Button.Pressed, "#confirm")
    def accept(self) -> None:
        if self.typed_matches():
            self.dismiss(ConfirmResult(ok=True, checked=self.checkbox_checked()))

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(ConfirmResult(ok=False, checked=False))


DANGER_CONFIRM_WORD = "YES"


class DangerConfirmModal(ConfirmModal):
    def __init__(self, question: str, checkbox: str | None = None) -> None:
        super().__init__(question, danger=True, checkbox=checkbox, require_typed=DANGER_CONFIRM_WORD)


class InputModal(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, title: str, placeholder: str, initial: str = "") -> None:
        super().__init__(classes="modal")
        self.title_text = title
        self.placeholder = placeholder
        self.initial = initial

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label(self.title_text, classes="modal-title")
            yield Input(value=self.initial, placeholder=self.placeholder, id="input-value")
            yield Label("Enter accept · Esc cancel", classes="modal-hint")

    @on(Input.Submitted, "#input-value")
    def accept(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if value:
            self.dismiss(value)

    def action_cancel(self) -> None:
        self.dismiss(None)


class TextAreaModal(ModalScreen[str | None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("ctrl+s", "save", "Save", priority=True),
    ]

    def __init__(self, title: str, initial: str) -> None:
        super().__init__(classes="modal")
        self.title_text = title
        self.initial = initial

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog -wide"):
            yield Label(self.title_text, classes="modal-title")
            yield TextArea(self.initial, id="text-value", soft_wrap=True)
            yield Label("Ctrl+S save · Esc cancel", classes="modal-hint")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Save", id="save", variant="primary")

    @on(Button.Pressed, "#save")
    def action_save(self) -> None:
        self.dismiss(self.query_one("#text-value", TextArea).text.strip())

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)


class SelectModal(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, title: str, options: list[tuple[str, str]], allow_new: bool = False) -> None:
        super().__init__(classes="modal")
        self.title_text = title
        self.options = options
        self.allow_new = allow_new

    def compose(self) -> ComposeResult:
        option_items = [Option(label, id=str(index)) for index, (label, _) in enumerate(self.options)]
        if self.allow_new:
            option_items.append(Option(Text("New…", style="italic"), id=NEW_OPTION_ID))
        with Vertical(classes="modal-dialog"):
            yield Label(self.title_text, classes="modal-title")
            yield OptionList(*option_items, id="select-options")
            yield Input(placeholder="New name", id="select-new")
            yield Label("Enter select · Esc cancel", classes="modal-hint")

    def on_mount(self) -> None:
        self.query_one("#select-new", Input).display = False
        self.query_one("#select-options", OptionList).focus()

    @on(OptionList.OptionSelected, "#select-options")
    def choose_option(self, event: OptionList.OptionSelected) -> None:
        if event.option.id == NEW_OPTION_ID:
            new_input = self.query_one("#select-new", Input)
            new_input.display = True
            new_input.focus()
            return
        self.dismiss(self.options[int(event.option.id or 0)][1])

    @on(Input.Submitted, "#select-new")
    def accept_new(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if value:
            self.dismiss(value)

    def action_cancel(self) -> None:
        self.dismiss(None)


def help_table(bindings: list[tuple[str, str]]) -> Table:
    table = Table(box=None, show_header=False, padding=(0, 1), expand=True)
    table.add_column(justify="right", style="bold", no_wrap=True, width=16)
    table.add_column(ratio=1)
    for key, description in bindings:
        table.add_row(key, description)
    return table


class HelpModal(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("question_mark", "close", "Close"),
        Binding("q", "close", "Close"),
    ]

    def __init__(self) -> None:
        super().__init__(classes="modal")

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog -wide"):
            yield Label("Keyboard shortcuts", classes="modal-title")
            with VerticalScroll(id="help-body"):
                for section_name, bindings in HELP_SECTIONS:
                    yield Static(Text(section_name, style="bold cyan"), classes="help-section")
                    yield Static(help_table(bindings))
            yield Label("Esc close", classes="modal-hint")

    def action_close(self) -> None:
        self.dismiss(None)
