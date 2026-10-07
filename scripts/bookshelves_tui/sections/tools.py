from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView

from bookshelves_tui.context import SectionWidget, app_of
from bookshelves_tui.flows import (
    run_doctor,
    run_force_reupload_all,
    run_generate,
    run_generate_force_covers,
    run_hard_reset_release,
    run_structure_log,
)
from bookshelves_tui.runner import NOT_RUN

if TYPE_CHECKING:
    from bookshelves_tui.app import BookshelvesApp

ToolFlow = Callable[["BookshelvesApp"], Awaitable[int | None]]


@dataclass(frozen=True)
class ToolSpec:
    tool_id: str
    label: str
    description: str
    flow: ToolFlow


@dataclass(frozen=True)
class ToolGroup:
    title: str
    tools: list[ToolSpec]
    danger: bool = False


async def run_smoke(app: BookshelvesApp) -> int:
    return await app.runner.run("smoke", app.runner.base_dir_args)


async def run_list(app: BookshelvesApp) -> int:
    return await app.runner.run("list", app.runner.base_dir_args)


async def show_help(app: BookshelvesApp) -> None:
    app.action_help()


TOOL_GROUPS = [
    ToolGroup("Checks", [
        ToolSpec("doctor", "Doctor", "Validate repo, metadata and covers (strict)", run_doctor),
        ToolSpec("smoke", "Smoke", "Check data contracts and the web app", run_smoke),
        ToolSpec("list", "List books", "Print every book, topic and category", run_list),
        ToolSpec("structure", "Structure log", "Regenerate library_structure.log", run_structure_log),
    ]),
    ToolGroup("Generate", [
        ToolSpec("generate", "Generate data", "Rebuild data.json and missing covers from Books/", run_generate),
        ToolSpec("generate-force", "Generate data (force covers)", "Rebuild data.json and every cover image",
                 run_generate_force_covers),
    ]),
    ToolGroup("Danger", [
        ToolSpec("upload-force", "Force re-upload all", "Dry-run, type YES, then overwrite every release asset",
                 run_force_reupload_all),
        ToolSpec("upload-hard-reset", "Hard reset release", "Dry-run, type YES, then delete the release and "
                 "re-upload all", run_hard_reset_release),
    ], danger=True),
    ToolGroup("", [
        ToolSpec("help", "Help [?]", "Show every key binding", show_help),
    ]),
]


class ToolHeading(ListItem):
    DEFAULT_CSS = """
    ToolHeading {
        height: 1;
        padding: 0 1;
        margin-top: 1;
        color: $text-muted;
        text-style: bold;
    }
    ToolHeading:first-child {
        margin-top: 0;
    }
    ToolHeading.-danger {
        color: $error;
    }
    """

    def __init__(self, title: str, danger: bool) -> None:
        super().__init__(Label(title.upper()), classes="-danger" if danger else "", disabled=True)


class ToolRow(ListItem):
    DEFAULT_CSS = """
    ToolRow {
        layout: horizontal;
        height: 1;
    }
    ToolRow .tool-status {
        width: 5;
        padding: 0 1;
        color: $text-muted;
    }
    ToolRow .tool-status.-ok {
        color: $success;
    }
    ToolRow .tool-status.-failed {
        color: $error;
    }
    ToolRow .tool-label {
        width: 30;
        text-style: bold;
        text-wrap: nowrap;
        text-overflow: ellipsis;
    }
    ToolRow.-spaced {
        margin-top: 1;
    }
    ToolRow.-danger .tool-label {
        color: $error;
    }
    ToolList > ToolRow.-danger.-highlight, ToolList:focus > ToolRow.-danger.-highlight {
        background: $error 70%;
    }
    ToolRow.-danger.-highlight .tool-label {
        color: $text;
    }
    ToolRow .tool-description {
        width: 1fr;
        color: $text-muted;
        text-wrap: nowrap;
        text-overflow: ellipsis;
    }
    """

    def __init__(self, tool: ToolSpec, danger: bool, spaced: bool) -> None:
        super().__init__(id=f"tool-{tool.tool_id}")
        self.tool = tool
        self.set_class(danger, "-danger")
        self.set_class(spaced, "-spaced")

    def compose(self) -> ComposeResult:
        yield Label("", classes="tool-status")
        yield Label(self.tool.label, classes="tool-label")
        yield Label(self.tool.description, classes="tool-description")

    def show_exit_code(self, exit_code: int) -> None:
        status = self.query_one(".tool-status", Label)
        status.update("✔" if exit_code == 0 else f"✖{exit_code}")
        status.set_class(exit_code == 0, "-ok")
        status.set_class(exit_code != 0, "-failed")


def tool_list_items(groups: list[ToolGroup]) -> list[ListItem]:
    items: list[ListItem] = []
    for group in groups:
        if group.title:
            items.append(ToolHeading(group.title, group.danger))
        items.extend(ToolRow(tool, group.danger, spaced=bool(items) and not group.title and index == 0)
                     for index, tool in enumerate(group.tools))
    return items


class ToolList(ListView):
    DEFAULT_CSS = """
    ToolList {
        height: 1fr;
    }
    """
    BINDINGS = [Binding("enter", "select_cursor", "Run")]

    def __init__(self, groups: list[ToolGroup]) -> None:
        items = tool_list_items(groups)
        first_tool_index = next(index for index, item in enumerate(items) if isinstance(item, ToolRow))
        super().__init__(*items, initial_index=first_tool_index, id="tools-list")

    @on(ListView.Highlighted)
    def reveal_group_heading(self, event: ListView.Highlighted) -> None:
        if event.item is None:
            return
        position = self.children.index(event.item)
        if position > 0 and isinstance(self.children[position - 1], ToolHeading):
            self.call_after_refresh(self.scroll_to_heading_and_row, self.children[position - 1], event.item)

    def scroll_to_heading_and_row(self, heading: Widget, row: Widget) -> None:
        self.scroll_to_region(heading.virtual_region_with_margin.union(row.virtual_region),
                              animate=False, immediate=True)

    @on(ListView.Selected)
    def run_selected_tool(self, event: ListView.Selected) -> None:
        if isinstance(event.item, ToolRow):
            self.run_tool(event.item)

    @work(group="tools")
    async def run_tool(self, row: ToolRow) -> None:
        exit_code = await row.tool.flow(app_of(self))
        if exit_code is not None and exit_code != NOT_RUN:
            row.show_exit_code(exit_code)


class ToolsSection(SectionWidget):
    def compose(self) -> ComposeResult:
        yield ToolList(TOOL_GROUPS)
