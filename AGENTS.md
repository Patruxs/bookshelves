# Bookshelves

A personal book library published as a static site at `Patruxs/bookshelves` (GitHub Pages, branch `main`).

| Path | Holds |
| --- | --- |
| `Books/` | Book files, organized by category and topic |
| `Inbox/` | New books waiting to be organized |
| `data/data.json` | Generated metadata for every book |
| `assets/covers/` | Generated cover images |
| `scripts/` | Python CLI and TUI |
| `web/` | React 19 + Astryx frontend, built with Vite |

## Workflow

1. Drop new books into `Inbox/`.
2. Run `bookshelves` and pick Auto-Organize (or `./book auto-organize`). The AI agent classifies the batch, writes `.cache/auto-organize-plan.json` and applies it with `./book apply-plan`, which moves the files, runs `generate`, sets descriptions, refreshes the structure log and runs `doctor`.
3. `./book doctor` to validate. Fix only issues about the current batch.
4. `./book upload` to preview, then `./book upload --execute` to push the files to GitHub Releases.
5. Commit and push. GitHub Actions builds `web/` and deploys it.

Ask the user once before: bulk move or rename, `apply-plan --execute`, real upload, `upload --force`, `upload --hard-reset`, `reset --execute`, git commit or push.

## Rules

Files on disk

- Book files (`*.pdf`, `*.epub`, `*.docx`) never go into git. They live on GitHub Releases under tag `storage-v1`.
- Layout: `Books/{N}_Category/Topic[/SubTopic]/Book_Title.pdf`. Folder and file names are ASCII `Snake_Case`, no diacritics.
- Covers are WebP, 600px wide, under 80KB.

Metadata

- `data/data.json` and `assets/covers/` contain generated data only. Never put HTML, CSS or JS there.
- `category` and `topic` use display names with spaces. A book in `Programming_Languages/Java/` has `"topic": "Programming Languages/Java"`.
- Never drop an existing `download_url` or `description`. If one is lost, restore with `git checkout data/data.json`.

## CLI

Run from the repo root: `./book <command>` (Windows: `book.bat <command>`). `--base-dir` defaults to the repo root.

Contract for every command:

- Commands that change files are dry runs unless `--execute` is given. `--yes` skips the confirmation prompt; without a terminal, `--execute` needs `--yes`.
- `--json` prints one JSON object on stdout; human output goes to stderr.
- Exit codes: `0` ok, `1` failure, `2` usage error or confirmation required. A cancel never exits `0`.

| Command | `--execute` | `--yes` | `--json` | Purpose |
| --- | --- | --- | --- | --- |
| `list` | | | yes | List books, topics and categories |
| `generate` | | | yes | Build covers and `data/data.json` from `Books/` (`--dry-run` to preview) |
| `doctor [--strict]` | | | yes | Validate repo, dependencies, metadata and covers |
| `smoke` | | | yes | Check data contracts and the web app (uses `web/dist` if built) |
| `structure` | | | yes | Regenerate `library_structure.log` |
| `apply-plan PLAN.json` | yes | yes | yes | Apply an Inbox plan `[{file, category, topic, description}]`: move, generate, describe, doctor |
| `rename` | yes | yes | yes | Normalize filenames in `Books/` and `Inbox/` |
| `unlock-pdfs` | yes | yes | yes | Strip passwords from PDFs in `Inbox/` |
| `epub-to-pdf` | yes | yes | yes | Convert EPUBs in `Inbox/` to PDF |
| `pdf-to-epub` | yes | yes | yes | Convert PDFs in `Inbox/` to image-based EPUB |
| `upload` | yes | yes | yes | Upload new books to GitHub Releases (`--force` / `--hard-reset` re-upload all, need `--yes`) |
| `delete --book "Title" [--delete-files]` | yes | yes | yes | Delete a book (`--topic "T" --category "C"` or `--category "C"` for groups) |
| `update --book "Title" --set-description/--set-category/--set-topic "X"` | yes | yes | yes | Edit book metadata (`--book-id ID` selects by exact id) |
| `update --topic "Old" --category "C" --rename "New"` | yes | yes | yes | Rename a topic (`--category "Old" --rename "New"` for a category) |
| `reset` | yes | yes | yes | Move `data/data.json`, covers and the structure log to `.backups/` |
| `auto-organize [--agent NAME] [--print-prompt] [--print-command] [--unsafe-permissions]` | | | `--list-agents` | Hand `Inbox/` to `claude`, `codex`, `opencode`, `gemini` or `cursor-agent` |
| `tui` | | | | Open the terminal UI (`scripts/bookshelves_tui/`, Textual) |

`rename --execute` clears `download_url` for renamed files, an exception to the `download_url` rule above: run `upload --execute` afterwards to restore it.
