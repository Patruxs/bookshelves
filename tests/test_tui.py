import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from textual.widgets import Button, DataTable, Input, Static, Tabs, Tree

import cli
from bookshelves_tui.app import BookshelvesApp
from bookshelves_tui.flows import parse_installed_agents, run_hard_reset_release, run_upload_new_books
from bookshelves_tui.modals import ConfirmResult, DangerConfirmModal, HelpModal
from bookshelves_tui.runner import OutputPane, StatusBar
from bookshelves_tui.sections.home import generate_status
from bookshelves_tui.sections.tools import ToolList

REPO_ROOT = Path(__file__).resolve().parents[1]
SCREEN_SIZE = (120, 40)
SAMPLE_BOOKS = [
    {"id": "a1", "title": "Clean_Code", "category": "Software Engineering", "topic": "Craft", "format": "pdf"},
    {"id": "b2", "title": "Database_Internals", "category": "Databases", "topic": "Storage", "format": "pdf"},
    {"id": "c3", "title": "Learning_SQL", "category": "Databases", "topic": "SQL", "format": "pdf"},
]
INBOX_FILE_NAMES = ["First Book.pdf", "second book.epub"]


@pytest.fixture
def base_dir(tmp_path: Path) -> Path:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "data.json").write_text(json.dumps(SAMPLE_BOOKS), encoding="utf-8")
    (tmp_path / "Inbox").mkdir()
    for name in INBOX_FILE_NAMES:
        (tmp_path / "Inbox" / name).write_bytes(b"book")
    return tmp_path


def book_leaves(tree: Tree) -> list:
    pending = list(tree.root.children)
    leaves = []
    while pending:
        node = pending.pop()
        if node.children:
            pending.extend(node.children)
        else:
            leaves.append(node)
    return leaves


@pytest.mark.asyncio
async def test_app_starts_with_stats_tabs_and_library_shortcut(base_dir: Path) -> None:
    app = BookshelvesApp(base_dir=base_dir)
    async with app.run_test(size=SCREEN_SIZE) as pilot:
        assert "3 books" in str(app.query_one("#header-stats", Static).render())
        assert app.query_one(Tabs).tab_count == 3
        assert app.query_one("#home") in app.focused.ancestors_with_self
        await pilot.press("2")
        await pilot.pause()
        assert app.focused is not None
        assert app.query_one("#library") in app.focused.ancestors_with_self


@pytest.mark.asyncio
async def test_library_tree_shows_categories_and_filter_narrows_to_one_book(base_dir: Path) -> None:
    app = BookshelvesApp(base_dir=base_dir)
    async with app.run_test(size=SCREEN_SIZE) as pilot:
        await pilot.press("2")
        await pilot.pause()
        tree = app.query_one("#library-tree", Tree)
        assert len(tree.root.children) == 2
        await pilot.press("slash")
        await pilot.pause()
        await pilot.press(*"learning sql")
        await pilot.pause()
        assert [str(leaf.label) for leaf in book_leaves(tree)] == ["Learning SQL"]


def enabled_library_actions(app: BookshelvesApp) -> set[str]:
    return {button.action_name for button in app.query(".library-action") if not button.disabled}


@pytest.mark.asyncio
async def test_library_action_buttons_follow_highlighted_node_and_run_their_action(
        base_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = BookshelvesApp(base_dir=base_dir)
    async with app.run_test(size=SCREEN_SIZE) as pilot:
        await pilot.press("2")
        await pilot.pause()
        assert enabled_library_actions(app) == {"rename", "delete"}
        await pilot.press("slash")
        await pilot.pause()
        await pilot.press(*"learning sql", "enter")
        await pilot.pause()
        assert enabled_library_actions(app) == {"edit", "move", "delete"}
        library = app.query_one("#library")
        moved: list[str] = []
        monkeypatch.setattr(library, "action_move", lambda: moved.append(library.highlighted_ref.title))
        await pilot.click("#library-action-move")
        await pilot.pause()
        assert moved == ["Learning_SQL"]


@pytest.mark.asyncio
async def test_library_hides_detail_pane_on_narrow_screen(base_dir: Path) -> None:
    app = BookshelvesApp(base_dir=base_dir)
    async with app.run_test(size=(70, 20)) as pilot:
        await pilot.press("2")
        await pilot.pause()
        assert not app.query_one("#library-detail-pane").display
        assert app.query_one("#library-actions").region.height == 1


@pytest.mark.asyncio
async def test_home_inbox_step_lists_inbox_files(base_dir: Path) -> None:
    app = BookshelvesApp(base_dir=base_dir)
    async with app.run_test(size=SCREEN_SIZE) as pilot:
        await pilot.pause()
        assert app.query_one("#inbox-table", DataTable).row_count == 2
        assert not app.query_one("#inbox-empty", Static).display


@pytest.mark.asyncio
async def test_empty_inbox_shows_empty_state(base_dir: Path) -> None:
    for path in (base_dir / "Inbox").iterdir():
        path.unlink()
    app = BookshelvesApp(base_dir=base_dir)
    async with app.run_test(size=SCREEN_SIZE) as pilot:
        await pilot.pause()
        empty_state = app.query_one("#inbox-empty", Static)
        assert empty_state.display
        assert "Drop" in str(empty_state.render())


@pytest.mark.asyncio
async def test_runner_streams_lines_and_returns_exit_code(base_dir: Path, tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    fake_script = tmp_path / "fake_command.py"
    fake_script.write_text("import sys\nfor n in (1, 2, 3):\n    print(f'line {n}')\nsys.exit(3)\n", encoding="utf-8")
    monkeypatch.setitem(cli.COMMANDS, "fake", {"script": str(fake_script), "inject_args": []})
    app = BookshelvesApp(base_dir=base_dir)
    async with app.run_test(size=SCREEN_SIZE) as pilot:
        exit_code = await app.runner.run("fake", [])
        await pilot.pause()
        logged = [line.text for line in app.query_one(OutputPane).log_view.lines]
        assert exit_code == 3
        assert [line for line in logged if line.startswith("line ")] == ["line 1", "line 2", "line 3"]
        assert logged[-1] == "✖ exit 3"
        assert str(app.query_one(StatusBar).render()) == "Failed (exit 3)"


def test_non_tty_entry_prints_help_and_exits_2() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "tui.py")],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 2
    assert "Usage:" in result.stdout


def record_runs(app: BookshelvesApp, monkeypatch: pytest.MonkeyPatch, confirm: ConfirmResult) -> list[list[str]]:
    calls: list[list[str]] = []

    async def fake_run(command: str, args: list[str]) -> int:
        calls.append([command, *args])
        return 0

    async def fake_push_screen_wait(screen: object) -> ConfirmResult:
        return confirm

    monkeypatch.setattr(app.runner, "run", fake_run)
    monkeypatch.setattr(app, "push_screen_wait", fake_push_screen_wait)
    return calls


@pytest.mark.asyncio
async def test_confirmed_preview_executes_with_execute_yes_and_checked_args(base_dir: Path,
                                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    app = BookshelvesApp(base_dir=base_dir)
    async with app.run_test(size=SCREEN_SIZE):
        calls = record_runs(app, monkeypatch, ConfirmResult(ok=True, checked=True))
        await app.runner.preview_then_execute("delete", ["--book-id", "a1"], "Delete?",
                                              checkbox="Also delete files", checked_args=["--delete-files"])
        assert calls == [
            ["delete", "--book-id", "a1"],
            ["delete", "--book-id", "a1", "--execute", "--yes", "--delete-files"],
        ]


@pytest.mark.asyncio
async def test_cancelled_preview_never_executes(base_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = BookshelvesApp(base_dir=base_dir)
    async with app.run_test(size=SCREEN_SIZE):
        calls = record_runs(app, monkeypatch, ConfirmResult(ok=False))
        assert await app.runner.preview_then_execute("rename", [], "Rename?") is None
        assert calls == [["rename"]]


@pytest.mark.asyncio
async def test_upload_flows_preview_with_same_flags_then_execute(base_dir: Path,
                                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    app = BookshelvesApp(base_dir=base_dir)
    async with app.run_test(size=SCREEN_SIZE):
        calls = record_runs(app, monkeypatch, ConfirmResult(ok=True))
        base_dir_args = ["--base-dir", str(base_dir.resolve())]
        await run_upload_new_books(app)
        await run_hard_reset_release(app)
        assert calls == [
            ["upload", *base_dir_args, "--dry-run"],
            ["upload", *base_dir_args, "--execute", "--yes"],
            ["upload", *base_dir_args, "--hard-reset", "--dry-run"],
            ["upload", *base_dir_args, "--hard-reset", "--execute", "--yes"],
        ]


@pytest.mark.asyncio
async def test_tools_list_moves_across_groups_and_enter_runs_highlighted_tool(base_dir: Path,
                                                                              monkeypatch: pytest.MonkeyPatch) -> None:
    app = BookshelvesApp(base_dir=base_dir)
    async with app.run_test(size=(70, 20)) as pilot:
        calls = record_runs(app, monkeypatch, ConfirmResult(ok=True))
        app.action_show_section("tools")
        await pilot.pause()
        assert app.focused is app.query_one(ToolList)
        await pilot.press("down", "down", "down", "down", "enter")
        await app.workers.wait_for_complete()
        assert calls == [["generate", "--base-dir", str(base_dir.resolve())]]
        await pilot.press(*["down"] * 10, "enter")
        await pilot.pause()
        assert isinstance(app.screen, HelpModal)


@pytest.mark.asyncio
async def test_home_keys_run_highlighted_step_and_upload_from_anywhere(base_dir: Path,
                                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    app = BookshelvesApp(base_dir=base_dir)
    async with app.run_test(size=SCREEN_SIZE) as pilot:
        calls = record_runs(app, monkeypatch, ConfirmResult(ok=True))
        base_dir_args = ["--base-dir", str(base_dir.resolve())]
        await pilot.press("down", "enter")
        await app.workers.wait_for_complete()
        await pilot.press("U")
        await app.workers.wait_for_complete()
        assert calls == [
            ["generate", *base_dir_args],
            ["upload", *base_dir_args, "--dry-run"],
            ["upload", *base_dir_args, "--execute", "--yes"],
        ]


def test_generate_status_detects_books_changed_after_data_json(base_dir: Path) -> None:
    book = base_dir / "Books" / "1_Category" / "Topic" / "Book.pdf"
    book.parent.mkdir(parents=True)
    book.write_bytes(b"book")
    for path in (book, book.parent, book.parent.parent, base_dir / "Books"):
        os.utime(path, (1_000, 1_000))
    data_json = base_dir / "data" / "data.json"
    os.utime(data_json, (2_000, 2_000))
    assert generate_status(base_dir).ok
    os.utime(book, (3_000, 3_000))
    assert not generate_status(base_dir).ok
    data_json.unlink()
    assert "missing" in generate_status(base_dir).text


@pytest.mark.asyncio
async def test_danger_confirm_needs_typed_yes(base_dir: Path) -> None:
    app = BookshelvesApp(base_dir=base_dir)
    async with app.run_test(size=SCREEN_SIZE) as pilot:
        app.push_screen(DangerConfirmModal("Hard reset?"))
        await pilot.pause()
        confirm_button = app.screen.query_one("#confirm", Button)
        await pilot.press(*"yes")
        assert confirm_button.disabled
        app.screen.query_one("#confirm-typed", Input).value = ""
        await pilot.press(*"YES")
        assert not confirm_button.disabled


def test_parse_installed_agents_reads_list_agents_json() -> None:
    report = {"agents": [
        {"name": "claude", "installed": True, "install_hint": ""},
        {"name": "codex", "installed": False, "install_hint": "npm i -g codex"},
    ]}
    assert parse_installed_agents(json.dumps(report)) == ["claude"]


def test_every_tui_command_is_registered_in_cli() -> None:
    used_commands = {"list", "doctor", "smoke", "generate", "upload", "structure", "update", "delete", "rename",
                     "unlock-pdfs", "epub-to-pdf", "pdf-to-epub", "auto-organize"}
    assert used_commands <= set(cli.COMMANDS)
