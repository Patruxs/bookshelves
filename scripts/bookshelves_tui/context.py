from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.dom import DOMNode
from textual.widget import Widget

if TYPE_CHECKING:
    from bookshelves_tui.app import BookshelvesApp
    from bookshelves_tui.runner import CommandRunner


def app_of(node: DOMNode) -> BookshelvesApp:
    return cast("BookshelvesApp", node.app)


class SectionWidget(Widget):
    @property
    def bookshelves_app(self) -> BookshelvesApp:
        return app_of(self)

    @property
    def runner(self) -> CommandRunner:
        return self.bookshelves_app.runner
