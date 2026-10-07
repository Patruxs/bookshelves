from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.widgets import Button, Input, Static, Tree
from textual.widgets.tree import TreeNode

from bookshelves_tui.context import SectionWidget
from bookshelves_tui.library import LibraryTree
from bookshelves_tui.modals import InputModal, SelectModal, TextAreaModal
from lib.book_paths import cover_filename
from lib.constants import COVER_DIR
from lib.json_io import Book, load_books
from lib.selection import categories_of, display_title, group_books, match_key, topics_of

CATEGORY = "category"
TOPIC = "topic"
BOOK = "book"
DESCRIPTION_MARKER = "●"
UPLOADED_MARKER = "↑"
DESCRIPTION_PREVIEW_LINES = 5
DESCRIPTION_PREVIEW_CHARS = 300
ACTION_BUTTONS = (
    ("edit", "Edit description [e]", frozenset({BOOK})),
    ("move", "Move [m]", frozenset({BOOK})),
    ("rename", "Rename [r]", frozenset({TOPIC, CATEGORY})),
    ("delete", "Delete [d]", frozenset({BOOK, TOPIC, CATEGORY})),
)


@dataclass(frozen=True)
class NodeRef:
    kind: str
    category: str
    topic: str = ""
    title: str = ""
    book_id: str = ""

    @property
    def parent(self) -> NodeRef | None:
        if self.kind == BOOK:
            return NodeRef(TOPIC, self.category, self.topic)
        if self.kind == TOPIC:
            return NodeRef(CATEGORY, self.category)
        return None


def book_matches(book: Book, query: str) -> bool:
    return match_key(query) in match_key(book.get("title", ""))


def duplicated_titles(books: list[Book]) -> set[str]:
    seen: set[str] = set()
    duplicated: set[str] = set()
    for book in books:
        title = display_title(book.get("title", ""))
        if title in seen:
            duplicated.add(title)
        seen.add(title)
    return duplicated


def title_with_format(book: Book) -> str:
    return f"{display_title(book.get('title', ''))} ({book.get('format', '')})"


def book_label(book: Book, show_format: bool = False) -> Text:
    label = Text(display_title(book.get("title", "")))
    if show_format:
        label.append(f" ({book.get('format', '')})", style="dim")
    if book.get("description"):
        label.append(f" {DESCRIPTION_MARKER}", style="cyan")
    if book.get("download_url"):
        label.append(f" {UPLOADED_MARKER}", style="green")
    return label


def description_preview(description: str) -> str:
    preview = "\n".join(description.strip().splitlines()[:DESCRIPTION_PREVIEW_LINES])
    if len(preview) > DESCRIPTION_PREVIEW_CHARS:
        preview = preview[:DESCRIPTION_PREVIEW_CHARS].rstrip() + "…"
    elif preview != description.strip():
        preview += "\n…"
    return preview


def count_label(name: str, count: int) -> Text:
    label = Text(name, style="bold")
    label.append(f" ({count})", style="dim")
    return label


class ActionButton(Button, can_focus=False):
    def __init__(self, label: str, action: str) -> None:
        super().__init__(Content(label), id=f"library-action-{action}", classes="library-action", compact=True, disabled=True)
        self.action_name = action


class LibrarySection(SectionWidget):
    SCOPED_CSS = False
    DEFAULT_CSS = """
    LibrarySection {
        layout: vertical;
    }

    LibrarySection #library-layout {
        height: 1fr;
    }

    LibrarySection #library-tree-pane {
        width: 3fr;
        height: 1fr;
    }

    LibrarySection #library-filter {
        dock: top;
    }

    LibrarySection #library-tree {
        height: 1fr;
    }

    LibrarySection #library-detail-pane {
        width: 2fr;
        height: 1fr;
        border-left: vkey $surface-lighten-2;
        padding: 0 1;
    }

    Screen.-compact LibrarySection #library-detail-pane {
        display: none;
    }

    LibrarySection #library-actions {
        height: 1;
        background: $boost;
    }

    LibrarySection .library-action {
        width: auto;
        min-width: 0;
        margin-right: 1;
    }
    """
    BINDINGS = [
        Binding("slash", "open_filter", "Filter", key_display="/"),
        Binding("escape", "clear_filter", "Clear filter", show=False),
        Binding("e", "edit", "Edit"),
        Binding("m", "move", "Move"),
        Binding("r", "rename", "Rename"),
        Binding("d", "delete", "Delete"),
    ]

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self.books: list[Book] = []
        self.library_tree: LibraryTree = {}
        self.filter_query = ""
        self.pending_selection: NodeRef | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="library-layout"):
            with Vertical(id="library-tree-pane"):
                tree: Tree[NodeRef] = Tree("Library", id="library-tree")
                tree.show_root = False
                yield tree
                yield Input(placeholder="Filter titles…", id="library-filter")
            with VerticalScroll(id="library-detail-pane"):
                yield Static("", id="library-detail")
        with Horizontal(id="library-actions"):
            for action, label, _ in ACTION_BUTTONS:
                yield ActionButton(label, action)

    def on_mount(self) -> None:
        self.filter_input.display = False
        self.reload()

    @property
    def base_dir(self) -> Path:
        return self.bookshelves_app.base_dir

    @property
    def tree_view(self) -> Tree[NodeRef]:
        return self.query_one("#library-tree", Tree)

    @property
    def filter_input(self) -> Input:
        return self.query_one("#library-filter", Input)

    @property
    def detail(self) -> Static:
        return self.query_one("#library-detail", Static)

    @property
    def highlighted_ref(self) -> NodeRef | None:
        node = self.tree_view.cursor_node
        return node.data if node is not None else None

    def reload(self, select: NodeRef | None = None) -> None:
        target = select or self.pending_selection or self.highlighted_ref
        try:
            self.books = load_books(self.base_dir)
        except (OSError, ValueError) as exc:
            self.books = []
            self.notify(f"Cannot read library: {exc}", severity="error")
        self.library_tree = group_books(self.books)
        self.rebuild_tree(target)

    def visible_tree(self) -> LibraryTree:
        if not self.filter_query:
            return self.library_tree
        filtered: LibraryTree = {}
        for category, topics in self.library_tree.items():
            for topic, books in topics.items():
                matching = [book for book in books if book_matches(book, self.filter_query)]
                if matching:
                    filtered.setdefault(category, {})[topic] = matching
        return filtered

    def rebuild_tree(self, target: NodeRef | None) -> None:
        tree = self.tree_view
        tree.clear()
        expand_all = bool(self.filter_query)
        nodes: dict[NodeRef, TreeNode[NodeRef]] = {}
        book_nodes_by_id: dict[str, TreeNode[NodeRef]] = {}
        book_nodes_by_title: dict[str, TreeNode[NodeRef]] = {}
        for category, topics in self.visible_tree().items():
            category_ref = NodeRef(CATEGORY, category)
            book_count = sum(len(books) for books in topics.values())
            category_node = tree.root.add(count_label(category, book_count), data=category_ref, expand=expand_all)
            nodes[category_ref] = category_node
            for topic, books in topics.items():
                topic_ref = NodeRef(TOPIC, category, topic)
                topic_node = category_node.add(count_label(topic, len(books)), data=topic_ref, expand=expand_all)
                nodes[topic_ref] = topic_node
                duplicated = duplicated_titles(books)
                for book in books:
                    book_ref = NodeRef(BOOK, category, topic, book.get("title", ""), book.get("id", ""))
                    show_format = display_title(book_ref.title) in duplicated
                    book_node = topic_node.add_leaf(book_label(book, show_format), data=book_ref)
                    nodes[book_ref] = book_node
                    book_nodes_by_id[book_ref.book_id] = book_node
                    book_nodes_by_title.setdefault(book_ref.title, book_node)
        self.restore_cursor(self.find_node(target, nodes, book_nodes_by_id, book_nodes_by_title))
        self.show_detail(self.highlighted_ref)

    def find_node(self, target: NodeRef | None, nodes: dict[NodeRef, TreeNode[NodeRef]],
                  book_nodes_by_id: dict[str, TreeNode[NodeRef]],
                  book_nodes_by_title: dict[str, TreeNode[NodeRef]]) -> TreeNode[NodeRef] | None:
        if target is None:
            return None
        if target.kind == BOOK and target not in nodes:
            if target.book_id in book_nodes_by_id:
                return book_nodes_by_id[target.book_id]
            if target.title in book_nodes_by_title:
                return book_nodes_by_title[target.title]
        ref: NodeRef | None = target
        while ref is not None:
            if ref in nodes:
                return nodes[ref]
            ref = ref.parent
        return None

    def restore_cursor(self, node: TreeNode[NodeRef] | None) -> None:
        if node is None:
            self.pending_selection = None
            self.tree_view.cursor_line = 0
            return
        ancestor = node.parent
        while ancestor is not None:
            ancestor.expand()
            ancestor = ancestor.parent
        self.select_after_refresh(node.data)

    def select_after_refresh(self, ref: NodeRef | None) -> None:
        self.pending_selection = ref
        self.call_after_refresh(self.apply_pending_selection)

    def apply_pending_selection(self) -> None:
        if self.pending_selection is None:
            return
        node = next((node for node in self.iter_nodes(self.tree_view.root) if node.data == self.pending_selection), None)
        self.pending_selection = None
        if node is not None:
            self.tree_view.move_cursor(node)
            self.show_detail(node.data)

    @on(Tree.NodeHighlighted, "#library-tree")
    def update_detail(self, event: Tree.NodeHighlighted[NodeRef]) -> None:
        self.show_detail(event.node.data)

    def find_book(self, ref: NodeRef) -> Book | None:
        return next((book for book in self.books if book.get("id") == ref.book_id), None)

    def update_actions(self, ref: NodeRef | None) -> None:
        for action, _, kinds in ACTION_BUTTONS:
            self.query_one(f"#library-action-{action}", ActionButton).disabled = ref is None or ref.kind not in kinds

    @on(Button.Pressed, ".library-action")
    async def run_action_button(self, event: Button.Pressed) -> None:
        event.stop()
        if isinstance(event.button, ActionButton):
            await self.run_action(event.button.action_name)

    def show_detail(self, ref: NodeRef | None) -> None:
        self.update_actions(ref)
        if ref is None:
            empty_text = "No books match the filter." if self.filter_query else "No books in data/data.json."
            self.detail.update(Text(empty_text, style="dim"))
        elif ref.kind == BOOK:
            self.detail.update(self.book_detail(ref))
        else:
            self.detail.update(self.group_detail(ref))

    def cover_path(self, book: Book) -> Path:
        if book.get("cover"):
            return self.base_dir / str(book["cover"])
        return self.base_dir / COVER_DIR / cover_filename(book.get("title", ""))

    def book_detail(self, ref: NodeRef) -> Text:
        book = self.find_book(ref)
        if book is None:
            return Text("Book not found.", style="dim")
        cover = self.cover_path(book)
        detail = Text()
        detail.append(display_title(book.get("title", "")), style="bold")
        detail.append(f"\n{ref.category} › {ref.topic}\n\n", style="cyan")
        description = book.get("description") or ""
        for field_name, value in (
            ("Format", book.get("format", "")),
            ("ID", book.get("id", "")),
            ("Upload", "uploaded" if book.get("download_url") else "not uploaded"),
            ("Description", "yes" if description else "none"),
        ):
            detail.append(f"{field_name}: ", style="bold")
            detail.append(f"{value}\n")
        detail.append("Cover: ", style="bold")
        detail.append(str(cover.relative_to(self.base_dir)) if cover.is_relative_to(self.base_dir) else str(cover))
        detail.append(" (exists)\n" if cover.exists() else " (missing)\n", style="green" if cover.exists() else "red")
        if description:
            detail.append("\n")
            detail.append(description_preview(description))
        return detail

    def group_detail(self, ref: NodeRef) -> Text:
        topics = self.library_tree.get(ref.category, {})
        books = topics.get(ref.topic, []) if ref.kind == TOPIC else [book for group in topics.values() for book in group]
        detail = Text()
        if ref.kind == TOPIC:
            detail.append(ref.topic, style="bold")
            detail.append(f"\n{ref.category}\n\n", style="cyan")
            detail.append(f"{len(books)} books\n\n")
        else:
            detail.append(ref.category, style="bold")
            detail.append(f"\n\n{len(books)} books · {len(topics)} topics\n\n")
        duplicated = duplicated_titles(books)
        for book in books:
            detail.append("• ")
            detail.append_text(book_label(book, display_title(book.get("title", "")) in duplicated))
            detail.append("\n")
        return detail

    def action_open_filter(self) -> None:
        self.filter_input.display = True
        self.filter_input.focus()

    def action_clear_filter(self) -> None:
        if not self.filter_input.display and not self.filter_query:
            return
        self.filter_input.value = ""
        self.filter_input.display = False
        self.apply_filter("")
        self.tree_view.focus()

    @on(Input.Changed, "#library-filter")
    def filter_changed(self, event: Input.Changed) -> None:
        self.apply_filter(event.value.strip())

    @on(Input.Submitted, "#library-filter")
    def filter_submitted(self) -> None:
        self.tree_view.focus()

    def apply_filter(self, query: str) -> None:
        if query == self.filter_query:
            return
        self.filter_query = query
        self.rebuild_tree(self.highlighted_ref)
        if query:
            first_book = next((node for node in self.iter_nodes(self.tree_view.root) if node.data and node.data.kind == BOOK), None)
            if first_book is not None:
                self.select_after_refresh(first_book.data)

    def iter_nodes(self, node: TreeNode[NodeRef]) -> Iterator[TreeNode[NodeRef]]:
        for child in node.children:
            yield child
            yield from self.iter_nodes(child)

    async def apply_update(self, command: str, args: list[str], question: str, select: NodeRef | None, *,
                           checkbox: str | None = None, checked_args: list[str] | None = None,
                           danger: bool = False) -> None:
        exit_code = await self.runner.preview_then_execute(command, [*args, *self.runner.base_dir_args], question,
                                                           checkbox=checkbox, checked_args=checked_args,
                                                           danger=danger)
        if exit_code is not None:
            self.pending_selection = select

    @work
    async def action_edit(self) -> None:
        ref = self.highlighted_ref
        if ref is None or ref.kind != BOOK:
            return
        book = self.find_book(ref) or {}
        description = await self.app.push_screen_wait(
            TextAreaModal(f"Description: {display_title(ref.title)}", book.get("description", ""))
        )
        if description is None or description == book.get("description", ""):
            return
        await self.apply_update("update", ["--book", ref.title, "--set-description", description],
                                "Apply this update?", ref)

    @work
    async def action_move(self) -> None:
        ref = self.highlighted_ref
        if ref is None or ref.kind != BOOK:
            return
        category = await self.app.push_screen_wait(SelectModal(
            f"Move {display_title(ref.title)}: category",
            [(name, name) for name in categories_of(self.books)],
            allow_new=True,
        ))
        if category is None:
            return
        topic = await self.app.push_screen_wait(SelectModal(
            f"Move {display_title(ref.title)}: topic in {category}",
            [(name, name) for name in topics_of(self.books, category)],
            allow_new=True,
        ))
        if topic is None:
            return
        change_args: list[str] = []
        if category != ref.category:
            change_args += ["--set-category", category]
        if topic != ref.topic:
            change_args += ["--set-topic", topic]
        if not change_args:
            self.notify("The book is already there.")
            return
        await self.apply_update("update", ["--book", ref.title, *change_args], "Apply this update?",
                                NodeRef(BOOK, category, topic, ref.title))

    @work
    async def action_rename(self) -> None:
        ref = self.highlighted_ref
        if ref is None or ref.kind == BOOK:
            return
        if ref.kind == TOPIC:
            new_name = await self.app.push_screen_wait(InputModal(f"Rename topic {ref.topic}", "New topic name", ref.topic))
            if new_name is None or new_name == ref.topic:
                return
            await self.apply_update("update", ["--topic", ref.topic, "--category", ref.category, "--rename", new_name],
                                    "Apply this update?", NodeRef(TOPIC, ref.category, new_name))
        else:
            new_name = await self.app.push_screen_wait(
                InputModal(f"Rename category {ref.category}", "New category name", ref.category)
            )
            if new_name is None or new_name == ref.category:
                return
            await self.apply_update("update", ["--category", ref.category, "--rename", new_name],
                                    "Apply this update?", NodeRef(CATEGORY, new_name))

    @work
    async def action_delete(self) -> None:
        ref = self.highlighted_ref
        if ref is None:
            return
        if ref.kind == BOOK:
            book = self.find_book(ref) or {"title": ref.title}
            await self.apply_update("delete", ["--book-id", ref.book_id], f"Delete {title_with_format(book)}?",
                                    ref.parent,
                                    checkbox="Also delete files from Books/", checked_args=["--delete-files"],
                                    danger=True)
        elif ref.kind == TOPIC:
            await self.apply_update("delete", ["--topic", ref.topic, "--category", ref.category],
                                    f"Delete topic {ref.topic} in {ref.category}?", ref.parent, danger=True)
        else:
            await self.apply_update("delete", ["--category", ref.category],
                                    f"Delete category {ref.category}?", None, danger=True)
