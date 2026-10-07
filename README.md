# 📚 My Bookshelves

A personal digital library: React + Astryx web app on GitHub Pages, AI-powered organization.

**[🌐 Download Book Here](https://patruxs.github.io/bookshelves/)**

## 🚀 Quick Start

```bash
git clone https://github.com/Patruxs/bookshelves.git
cd bookshelves

# Setup (installs dependencies & creates folders)
setup.bat               # Windows
chmod +x setup.sh && ./setup.sh  # macOS / Linux

# View locally
cd web && npm ci && npm run dev
# → http://localhost:5173/bookshelves/
```

## 🔄 Adding Books

1. Drop book files into `Inbox/`.
2. Run `bookshelves` (or `./bookshelves` from the repo root, `bookshelves.bat` on Windows).
3. Pick **Auto-Organize**: an installed AI agent (Claude Code, Codex, opencode, Gemini CLI or Cursor Agent) classifies, describes and uploads the books.
   The agent writes a plan and applies it with `./book apply-plan`. Set `BOOKSHELVES_AGENT` (or `--agent`) to pick the agent; `./book auto-organize --print-prompt` shows the prompt it gets.
4. Push to `main` (auto-deploys via GitHub Actions).

## 🧰 Management

Manage your library using the interactive terminal UI:
```bash
# Windows cmd.exe, or after adding the repo to PATH
book tui

# Windows PowerShell from the repo root
.\book.bat tui

# macOS / Linux
./book tui
```

The TUI is a full-screen app: press `?` for help and `1`-`5` to switch sections.

Short CLI examples:
```bash
./book doctor
./book unlock-pdfs
./book epub-to-pdf
./book pdf-to-epub
./book generate
./book apply-plan plan.json
```

> **Note:** Book files (`*.pdf`, `*.epub`) are stored in GitHub Releases, not Git. Run `./book doctor` to validate repository health.
