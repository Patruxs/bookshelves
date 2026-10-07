# TUI

`bookshelves` (or `book tui`) opens a full-screen Textual app in `scripts/bookshelves_tui/`. The
TUI holds no library logic: every action runs a script through `cli.COMMANDS`, so the CLI stays
the single source of truth. Every action that changes files does a dry run first, then asks for
confirmation, then runs with `--execute --yes`. On a non-tty, `scripts/tui.py` prints usage and
exits with code 2.

## Layout

```
 📚 My Bookshelves                        173 books · 5 categories · Inbox: 2
 1 Home │ 2 Library │ 3 Tools
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                         CONTENT (active tab)                            │
 └─────────────────────────────────────────────────────────────────────────┘
 Running: generate
 ╭ Output ─────────────────────────────────────────────────────────────────╮
 │ ▸ python scripts/generate_data.py --base-dir …                          │
 ╰─────────────────────────────────────────────────────────────────────────╯
 ⏎ Run step  o Output  ^l Clear output  ? Help  q Quit
```

- **Header**: title, and stats that refresh after every command.
- **Tabs**: `1` `2` `3` switch tabs and focus their content. The tab strip itself never takes focus.
- **Status bar**: `Idle`, `Running: <command args>`, `Done (exit 0)` or `Failed (exit N)`. It stays
  visible when the output pane is hidden.
- **Output pane**: streams stdout and stderr, framed by `▸ <argv>` and `✔ exit 0` / `✖ exit N`
  lines. `o` cycles default / maximised / hidden, and `Ctrl+L` clears it.
- **Compact** (terminal below 80x24): the screen gets the `-compact` class. The output pane shrinks
  to 25%, Home steps lose their spacing, the Inbox table caps at 4 rows and its buttons wrap into a
  3-column grid, and Library hides the detail panel.

## Home

The publish workflow as a list of steps. Each step shows a status (`✔` done, `●` needs attention)
and buttons that show their key. Up/Down highlights a step, Enter runs its first button, and the
letter keys work from anywhere in Home. Statuses refresh after every command.

| Step | Buttons | Status |
| --- | --- | --- |
| 1 Inbox | Auto-Organize `a`, Unlock PDFs `u`, EPUB→PDF `p`, PDF→EPUB `b`, Rename `n` | `N files waiting` / `empty`, plus a table of `Inbox/` files |
| 2 Generate | Generate `g` | `up to date` / `Books/ changed since last generate` (something under `Books/` is newer than `data.json`) / `data.json missing` |
| 3 Doctor | Doctor `d` | `OK`/`FAILED` · errors · warnings of the last run in this session, or `not run yet` |
| 4 Upload | Upload new books `U` | `N books not uploaded` (no `download_url`) / `all uploaded` |
| 5 Commit | none | hint: git add / commit / push in your shell |

Auto-Organize lists the installed agents (`auto-organize --list-agents --json`), asks for
confirmation, then hands the terminal to the agent via `App.suspend()`. Upload runs
`upload --dry-run`, asks for confirmation, then runs the real upload.

## Library

A tree of Category › Topic › Book from `data/data.json`, with counts on group nodes. Book nodes
show `●` when the book has a description and `↑` when it is uploaded. The detail panel on the right
shows either the book's metadata, cover state and description preview, or the book list of a
topic or category. `/` filters titles and Esc clears the filter.

The action bar under the tree has buttons that enable for the highlighted node kind:

| Key | Node | Command |
| --- | --- | --- |
| `e` | book | `update --set-description` |
| `m` | book | `update --set-category` / `--set-topic` |
| `r` | topic, category | `update --rename` |
| `d` | book, topic, category | `delete` (book: optional `--delete-files`) |

After a change the tree reloads and the cursor returns to the same node, or to its parent if the
node is gone.

## Tools

A grouped list. Up/Down moves between rows and Enter runs the highlighted one.

- **Checks**: Doctor (`--strict`, which also updates the Home Doctor step), Smoke, List books, Structure log
- **Generate**: Generate data, Generate data (force covers)
- **Danger**: Force re-upload all, Hard reset release. Each does a dry run first, then opens
  `DangerConfirmModal`, where Confirm stays disabled until the user types `YES`.
- Help

## Files

```
scripts/tui.py                entry point: tty check, --help, main()
scripts/bookshelves_tui/
  app.py                      BookshelvesApp: header, tabs, bindings, compact class, last_doctor_report
  app.tcss                    shared styles (Library and Tools carry their own DEFAULT_CSS)
  runner.py                   CommandRunner, StatusBar, OutputPane
  flows.py                    command flows shared by Home and Tools, DoctorReport
  modals.py                   Confirm, DangerConfirm, Input, TextArea, Select, Help modals
  library.py                  stats and Inbox listing
  context.py                  SectionWidget base
  sections/home.py            Home steps
  sections/library.py         Library tree, detail panel, action bar
  sections/tools.py           grouped Tools list
tests/test_tui.py             Textual pilot tests against a temporary base dir
```
