# Bookshelves

Personal book library published as a static site at `Patruxs/bookshelves` (GitHub Pages, branch `main`).

| Path | Holds |
| --- | --- |
| `Books/` | Book files by category and topic |
| `Inbox/` | New books waiting to be organized |
| `data/data.json` | Generated metadata for every book |
| `assets/covers/` | Generated WebP covers |
| `scripts/` | Python CLI and Textual TUI |
| `web/` | React 19 + Astryx frontend, built with Vite |
| `tests/` | pytest suite (`pytest`, lint with `ruff`) |

## Workflow

1. Drop new books into `Inbox/`.
2. `./book auto-organize` (or `bookshelves` → Auto-Organize). The agent classifies the batch into `.cache/auto-organize-plan.json`, then `./book apply-plan` moves files, runs `generate`, sets descriptions, refreshes the structure log and runs `doctor`.
3. `./book doctor`. Fix only issues from the current batch.
4. `./book upload` to preview, `./book upload --execute` to push files to GitHub Releases.
5. Commit and push. GitHub Actions builds `web/` and deploys.

Ask the user once before: bulk move or rename, `apply-plan --execute`, real upload, `upload --force`, `upload --hard-reset`, `reset --execute`, git commit or push.

## Rules

- Book files (`*.pdf`, `*.epub`, `*.docx`) never go into git. They live on GitHub Releases under tag `storage-v1`.
- Layout: `Books/{N}_Category/Topic[/SubTopic]/Book_Title.pdf`. Names are ASCII `Snake_Case`, no diacritics.
- Covers: WebP, 600px wide, under 80KB.
- `data/data.json` and `assets/covers/` hold generated data only. No HTML, CSS or JS.
- `category` and `topic` use display names with spaces. `Programming_Languages/Java/` → `"topic": "Programming Languages/Java"`.
- Never drop an existing `download_url` or `description`. Restore with `git checkout data/data.json`.

## CLI

Run from the repo root: `./book <command>` (Windows: `book.bat`).

- Commands that change files are dry runs unless `--execute` is given. `--yes` skips confirmation and is required with `--execute` when there is no terminal.
- `--json` prints one JSON object on stdout; human output goes to stderr.
- Exit codes: `0` ok, `1` failure, `2` usage error or confirmation required. A cancel never exits `0`.

| Command | Changes files | Purpose |
| --- | --- | --- |
| `list` | | List books, topics and categories |
| `generate [--dry-run]` | | Build covers and `data/data.json` from `Books/` |
| `doctor [--strict]` | | Validate repo, dependencies, metadata and covers |
| `smoke` | | Check data contracts and the web app (uses `web/dist` if built) |
| `structure` | | Regenerate `library_structure.log` |
| `auto-organize [--agent NAME] [--print-prompt] [--print-command] [--unsafe-permissions] [--list-agents]` | | Hand `Inbox/` to `claude`, `codex`, `opencode`, `gemini` or `cursor-agent` |
| `tui` | | Open the terminal UI |
| `apply-plan PLAN.json` | yes | Apply an Inbox plan `[{file, category, topic, description}]` |
| `rename` | yes | Normalize filenames in `Books/` and `Inbox/` |
| `unlock-pdfs` | yes | Strip passwords from PDFs in `Inbox/` |
| `epub-to-pdf` / `pdf-to-epub` | yes | Convert files in `Inbox/` |
| `upload [--force \| --hard-reset]` | yes | Upload new books to GitHub Releases (`--force` and `--hard-reset` re-upload all, need `--yes`) |
| `delete --book "Title" [--delete-files]` | yes | Delete a book; `--topic "T" --category "C"` or `--category "C"` for groups |
| `update --book "Title" --set-description/--set-category/--set-topic "X"` | yes | Edit book metadata (`--book-id ID` selects by exact id) |
| `update --topic "Old" --category "C" --rename "New"` | yes | Rename a topic (`--category "Old" --rename "New"` for a category) |
| `reset` | yes | Move `data/data.json`, covers and the structure log to `.backups/` |

`rename --execute` clears `download_url` for renamed files; run `upload --execute` afterwards to restore it.
