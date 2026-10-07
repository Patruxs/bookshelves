from __future__ import annotations

from pathlib import Path

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Footer, Static, TabbedContent, TabPane, Tabs

from bookshelves_tui.flows import DoctorReport
from bookshelves_tui.library import read_stats
from bookshelves_tui.modals import HelpModal
from bookshelves_tui.runner import CommandFinished, CommandRunner, OutputPane, StatusBar
from bookshelves_tui.sections.home import HomeSection
from bookshelves_tui.sections.library import LibrarySection
from bookshelves_tui.sections.tools import ToolsSection

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_TITLE = "📚 My Bookshelves"
MIN_WIDTH = 80
MIN_HEIGHT = 24
OUTPUT_MODES = ("default", "maximised", "hidden")
TAB_ID_PREFIX = "tab-"

SECTIONS: list[tuple[str, str, type[Widget]]] = [
    ("home", "Home", HomeSection),
    ("library", "Library", LibrarySection),
    ("tools", "Tools", ToolsSection),
]


class AppHeader(Horizontal):
    def compose(self) -> ComposeResult:
        yield Static(APP_TITLE, id="header-title")
        yield Static("", id="header-stats")

    def show_stats(self, text: str) -> None:
        self.query_one("#header-stats", Static).update(text)


class BookshelvesApp(App[None]):
    CSS_PATH = "app.tcss"
    TITLE = APP_TITLE
    BINDINGS = [
        *(Binding(str(index), f"show_section('{section_id}')", name, show=False)
          for index, (section_id, name, _) in enumerate(SECTIONS, start=1)),
        Binding("o", "cycle_output", "Output"),
        Binding("ctrl+l", "clear_output", "Clear output"),
        Binding("question_mark", "help", "Help", key_display="?"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, base_dir: Path) -> None:
        super().__init__()
        self.base_dir = base_dir.resolve()
        self.runner = CommandRunner(self, self.base_dir)
        self.output_mode = OUTPUT_MODES[0]
        self.last_doctor_report: DoctorReport | None = None

    def compose(self) -> ComposeResult:
        yield AppHeader(id="header")
        with Vertical(id="main"):
            with TabbedContent(initial=TAB_ID_PREFIX + SECTIONS[0][0], id="sections"):
                for index, (section_id, name, section_class) in enumerate(SECTIONS, start=1):
                    with TabPane(f"{index} {name}", id=TAB_ID_PREFIX + section_id):
                        yield section_class(id=section_id)
            yield StatusBar(id="status-bar")
            yield OutputPane(id="output")
        yield Footer(compact=True, show_command_palette=False)

    def on_mount(self) -> None:
        self.query_one("#sections", TabbedContent).query_one(Tabs).can_focus = False
        self.update_compact_layout(self.size.width, self.size.height)
        self.refresh_stats()
        self.focus_section(SECTIONS[0][0])

    def refresh_stats(self) -> None:
        stats = read_stats(self.base_dir)
        inbox_text = f"Inbox: {stats.inbox_files}" if stats.inbox_files else "Inbox: empty"
        self.query_one(AppHeader).show_stats(
            f"{stats.books} books · {stats.categories} categories · {inbox_text}"
        )

    def on_command_finished(self, message: CommandFinished) -> None:
        self.refresh_stats()
        self.reload_sections()

    def reload_sections(self) -> None:
        for section_id, _, _ in SECTIONS:
            reload = getattr(self.query_one(f"#{section_id}"), "reload", None)
            if callable(reload):
                reload()

    def on_resize(self, event: events.Resize) -> None:
        self.update_compact_layout(event.size.width, event.size.height)

    def update_compact_layout(self, width: int, height: int) -> None:
        self.screen.set_class(width < MIN_WIDTH or height < MIN_HEIGHT, "-compact")

    def show_section(self, section_id: str) -> None:
        self.query_one("#sections", TabbedContent).active = TAB_ID_PREFIX + section_id

    def focus_section(self, section_id: str) -> None:
        section = self.query_one(f"#{section_id}")
        for widget in (section, *section.query("*")):
            if widget.focusable:
                widget.focus()
                return

    def action_show_section(self, section_id: str) -> None:
        self.show_section(section_id)
        self.focus_section(section_id)

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        focus_is_in_pane = self.focused is not None and event.pane in self.focused.ancestors
        if event.tabbed_content.id == "sections" and event.pane.id and not focus_is_in_pane:
            self.focus_section(event.pane.id.removeprefix(TAB_ID_PREFIX))

    def action_cycle_output(self) -> None:
        next_index = (OUTPUT_MODES.index(self.output_mode) + 1) % len(OUTPUT_MODES)
        self.output_mode = OUTPUT_MODES[next_index]
        main = self.query_one("#main")
        main.set_class(self.output_mode == "hidden", "-output-hidden")
        main.set_class(self.output_mode == "maximised", "-output-maximised")

    def action_clear_output(self) -> None:
        self.query_one(OutputPane).clear()

    def action_help(self) -> None:
        if not isinstance(self.screen, HelpModal):
            self.push_screen(HelpModal())


def main(base_dir: Path = REPO_ROOT) -> None:
    BookshelvesApp(base_dir=base_dir).run()
