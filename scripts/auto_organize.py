#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from lib.cli_common import (
    EXIT_FAILURE,
    EXIT_OK,
    INTERRUPTED_EXIT_CODE,
    add_base_dir_arg,
    add_json_arg,
    run_main,
)
from lib.constants import BOOK_EXTENSIONS, BOOKS_DIR, CATEGORY_PATTERN, INBOX_DIR
from lib.output import emit_json
from lib.validation import validate_library

AGENT_ENV_VAR = "BOOKSHELVES_AGENT"
PROMPT_PLACEHOLDER = "{prompt}"
SIGNAL_EXIT_BASE = 128
CACHE_DIR = ".cache"
PROMPT_FILE = f"{CACHE_DIR}/auto-organize-prompt.md"
PLAN_FILE = f"{CACHE_DIR}/auto-organize-plan.json"
AGENT_INSTRUCTION = f"Read {PROMPT_FILE} and follow it exactly"

CLAUDE_ALLOWED_TOOLS = [
    "Bash(./book apply-plan:*)",
    "Bash(./book doctor:*)",
    "Bash(./book structure:*)",
    "Bash(./book rename:*)",
    "Bash(./book upload --dry-run:*)",
    "Read",
    "Write(.cache/**)",
    "Edit(.cache/**)",
    "Glob",
    "Grep",
]


class AgentSpec(NamedTuple):
    build_argv: Callable[[str], list[str]]
    install_hint: str
    permission_args: list[str]


AGENTS: dict[str, AgentSpec] = {
    "claude": AgentSpec(
        lambda prompt: ["claude", prompt],
        "npm install -g @anthropic-ai/claude-code",
        ["--allowedTools", ",".join(CLAUDE_ALLOWED_TOOLS)],
    ),
    "codex": AgentSpec(lambda prompt: ["codex", prompt], "npm install -g @openai/codex", ["-a", "on-request"]),
    "opencode": AgentSpec(lambda prompt: ["opencode", "--prompt", prompt], "npm install -g opencode-ai", []),
    "gemini": AgentSpec(
        lambda prompt: ["gemini", "--prompt-interactive", prompt], "npm install -g @google/gemini-cli", []
    ),
    "cursor-agent": AgentSpec(
        lambda prompt: ["cursor-agent", prompt], "curl https://cursor.com/install -fsS | bash", []
    ),
}

ROUTING_HINTS = [
    ("React", "1_Computer_Science_Fundamentals/Programming_Languages/React"),
    ("Other programming languages", "1_Computer_Science_Fundamentals/Programming_Languages/<Language>"),
    ("System design and architecture", "2_Software_Engineering/Software_Architecture_and_Design"),
    ("DevOps, cloud and AWS", "2_Software_Engineering/DevOps"),
    ("Docker", "2_Software_Engineering/Docker"),
    ("Kubernetes", "2_Software_Engineering/Kubernetes"),
    ("Databases", "2_Software_Engineering/Database"),
    ("Interviews", "3_Career_and_Professional_Development/Interview_Prep"),
    ("Job search and career growth", "3_Career_and_Professional_Development/Job_Search_and_Career_Growth"),
    ("English and language learning", "4_Personal_Development_and_Skills/English_Learning"),
    ("Vietnamese university course materials", "5_University_Courses"),
]

AUTO_ORGANIZE_PROMPT = r"""## Procedure

1. Preview filename normalization with `./book rename`. If files would be renamed, show the preview, ask the user once, then run `./book rename --execute --yes` and use the new names from here on.
2. Classify every book in memory into `Books/{category}/{topic}[/{subtopic}]/`:
   - Use the AVAILABLE CATEGORIES above. Prefer existing folders and be specific.
   - Use filename clues: title, author, edition, keywords.
   - Create a new topic (`Snake_Case`) or category (`{N}_Snake_Case`, N = next free number) only when nothing existing fits; do not create one per book.
3. Write a description for every book, as three prose parts without labels such as `Context:` or `Overview:`:
   1. Context: the problem or challenge the book addresses.
   2. Overview: the book, its author and its approach.
   3. Takeaways: 4-5 `•` bullets, each starting with a verb (Master, Build, Learn, Explore, Implement).

   Separate the parts with a blank line. Choose the language once from the filename and never mix languages:
   - Vietnamese if the filename has Vietnamese diacritics or Vietnamese words or patterns, even without diacritics (`Ch01_`, `Giao_trinh_`, `Bai_giang_`, `PTTKHT`, `Thuong_mai_dien_tu`, `Quan_tri_`, `AI_co_ban`, `Kien_truc_ung_dung`).
   - English otherwise.

   If the user gave a source link, append it as a last part: `Link source : <a href="URL" target="_blank">URL</a>`.
4. Write the whole batch to `{plan_file}` as a JSON array, one object per book:
   ```json
   [{"file": "Inbox/Book_Name.pdf", "category": "2_Software_Engineering", "topic": "DevOps", "description": "Context...\n\nOverview...\n\n• Master ..."}]
   ```
   `topic` is the folder path below the category, for example `Programming_Languages/React`.
5. Preview the plan with `./book apply-plan {plan_file}`. Fix the plan file until it reports no errors.
6. Show the user the preview table and ask once. If they request changes, edit the plan file and preview again. Continue only after approval.
7. Apply it with `./book apply-plan {plan_file} --execute --yes --json`. It moves the files, runs generate, sets the descriptions, refreshes the structure log and runs doctor. If it exits non-zero, show the `error` field to the user and STOP.
8. Run `./book doctor --json`. Fix only errors about books from this batch; report any other issue to the user without touching it.
9. Preview the upload with `./book upload --dry-run`. The count must equal N; if it is greater, STOP. Ask the user once, then run `./book upload --execute`.
10. Ask the user once, then commit and push:
    ```bash
    git add -A && git commit -m "add: N books to library" && git push
    ```
11. Report:
    ```
    Complete: N books processed
    | # | Book | Destination | Cover | Description | Upload |
    Links: ?book={id1}, ?book={id2}, ...
    ```
"""


class UnknownAgentError(ValueError):
    pass


def agent_binary(name: str) -> str:
    return AGENTS[name].build_argv("")[0]


def list_inbox_books(base_dir: Path) -> list[str]:
    inbox = base_dir / INBOX_DIR
    if not inbox.is_dir():
        return []
    return sorted(
        entry.name
        for entry in inbox.iterdir()
        if entry.is_file() and entry.suffix.lower() in BOOK_EXTENSIONS
    )


def category_sort_key(folder: Path) -> tuple[int, str]:
    match = CATEGORY_PATTERN.match(folder.name)
    return (int(match.group(1)) if match else sys.maxsize, folder.name)


def list_categories(base_dir: Path) -> list[Path]:
    books_dir = base_dir / BOOKS_DIR
    if not books_dir.is_dir():
        return []
    return sorted((folder for folder in books_dir.iterdir() if folder.is_dir()), key=category_sort_key)


def topic_paths(category: Path) -> list[str]:
    return sorted(
        folder.relative_to(category).as_posix()
        for folder in category.rglob("*")
        if folder.is_dir() and not folder.name.startswith(".")
    )


def render_categories(base_dir: Path) -> str:
    categories = list_categories(base_dir)
    lines = ["## AVAILABLE CATEGORIES (folders under Books/)", ""]
    for category in categories:
        lines.append(f"- {category.name}")
        lines.extend(f"  - {topic}" for topic in topic_paths(category))
    numbers = [int(match.group(1)) for match in (CATEGORY_PATTERN.match(c.name) for c in categories) if match]
    lines.extend(["", f"Next free category number: {max(numbers, default=0) + 1}"])
    return "\n".join(lines)


def render_routing_hints(base_dir: Path) -> str:
    books_dir = base_dir / BOOKS_DIR
    hints = [
        f"- {subject} -> `{folder}`"
        for subject, folder in ROUTING_HINTS
        if (books_dir / folder.split("/<", 1)[0]).is_dir()
    ]
    if not hints:
        return ""
    return "## Routing hints\n\n" + "\n".join(hints)


def build_prompt(base_dir: Path, books: list[str]) -> str:
    book_lines = "\n".join(f"- {INBOX_DIR}/{name}" for name in books) or "- (none)"
    sections = [
        "You are organizing the Inbox of this repository. Read AGENTS.md first and obey its hard rules.",
        "Run every command from the repo root exactly as written. Use only `./book ...` commands, never python. "
        "Classify the whole batch in memory and ask the user once per step that says so; never ask book by book.",
        f"{INBOX_DIR}/ has N = {len(books)} new books:\n{book_lines}",
        render_categories(base_dir),
        render_routing_hints(base_dir),
        AUTO_ORGANIZE_PROMPT.replace("{plan_file}", PLAN_FILE),
    ]
    return "\n\n".join(section for section in sections if section)


def write_prompt_file(base_dir: Path, prompt: str) -> Path:
    prompt_path = base_dir / PROMPT_FILE
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt, encoding="utf-8", newline="\n")
    return prompt_path


def resolve_agent_choice(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    from_env = os.environ.get(AGENT_ENV_VAR, "").strip()
    if from_env:
        return from_env
    return next((name for name in AGENTS if shutil.which(agent_binary(name))), None)


def build_agent_argv(choice: str, instruction: str, *, unsafe_permissions: bool) -> list[str]:
    if PROMPT_PLACEHOLDER in choice:
        return [token.replace(PROMPT_PLACEHOLDER, instruction) for token in shlex.split(choice)]
    if choice not in AGENTS:
        raise UnknownAgentError(choice)
    spec = AGENTS[choice]
    argv = spec.build_argv(instruction)
    return argv if unsafe_permissions else [*argv, *spec.permission_args]


def print_install_hints() -> None:
    print("❌ No supported AI agent found on PATH. Install one of:", file=sys.stderr)
    for name, spec in AGENTS.items():
        print(f"   {name:<14} {spec.install_hint}", file=sys.stderr)
    print(f"   Or pass --agent \"<command> {PROMPT_PLACEHOLDER}\" for another agent.", file=sys.stderr)


def report_unknown_agent(choice: str) -> None:
    print(f"❌ Unknown agent: \"{choice}\"", file=sys.stderr)
    print(f"   Supported: {', '.join(AGENTS)}", file=sys.stderr)
    print(f"   Or pass a command template containing {PROMPT_PLACEHOLDER}.", file=sys.stderr)


def report_missing_binary(choice: str, binary: str) -> None:
    print(f"❌ Agent command not found: {binary}", file=sys.stderr)
    if choice in AGENTS:
        print(f"   Install: {AGENTS[choice].install_hint}", file=sys.stderr)


def agent_statuses() -> list[dict[str, object]]:
    return [
        {
            "name": name,
            "installed": shutil.which(agent_binary(name)) is not None,
            "install_hint": spec.install_hint,
        }
        for name, spec in AGENTS.items()
    ]


def print_agents(*, as_json: bool) -> None:
    if as_json:
        emit_json({"agents": agent_statuses()})
        return
    for name in AGENTS:
        location = shutil.which(agent_binary(name))
        status = f"found      {location}" if location else f"not found  install: {AGENTS[name].install_hint}"
        print(f"{name:<14} {status}")


def exit_code_from_returncode(returncode: int) -> int:
    if returncode < 0:
        return SIGNAL_EXIT_BASE - returncode
    return returncode


def launch_agent(choice: str, argv: list[str], base_dir: Path) -> int:
    executable = shutil.which(argv[0])
    if executable is None:
        report_missing_binary(choice, argv[0])
        return EXIT_FAILURE
    print(f"🤖 Launching {choice if choice in AGENTS else argv[0]}...", flush=True)
    try:
        result = subprocess.run([executable, *argv[1:]], cwd=base_dir)
    except KeyboardInterrupt:
        return INTERRUPTED_EXIT_CODE
    return exit_code_from_returncode(result.returncode)


def print_git_status(base_dir: Path) -> None:
    git = shutil.which("git")
    if git is None:
        return
    result = subprocess.run([git, "status", "--short"], cwd=base_dir, capture_output=True, text=True, encoding="utf-8")
    print("\n📋 git status --short:")
    if result.returncode != 0:
        print(f"   {result.stderr.strip()}")
        return
    print(result.stdout.rstrip() or "   (clean)")


def verify_after_agent(base_dir: Path) -> int:
    validation = validate_library(base_dir, include_dependencies=False)
    leftover = list_inbox_books(base_dir)
    error_count = validation["summary"]["errors"]
    print(f"\n🩺 Doctor: {error_count} error(s), {validation['summary']['warnings']} warning(s)")
    for issue in validation["errors"]:
        print(f"   - [{issue['code']}] {issue['message']} ({issue['file']})")
    if leftover:
        print(f"📥 {INBOX_DIR}/ still has {len(leftover)} book(s):")
        for name in leftover:
            print(f"   - {name}")
    else:
        print(f"📭 {INBOX_DIR}/ is empty.")
    print_git_status(base_dir)
    return EXIT_FAILURE if leftover or error_count else EXIT_OK


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=os.environ.get("BOOK_PROG"),
        description="Launch an AI agent to classify Inbox books",
    )
    add_base_dir_arg(parser)
    parser.add_argument(
        "--agent",
        help=f"Agent name ({', '.join(AGENTS)}) or a command template containing {PROMPT_PLACEHOLDER}; "
        f"defaults to ${AGENT_ENV_VAR}, then the first installed agent",
    )
    parser.add_argument("--list-agents", action="store_true", help="Show supported agents and whether they are installed")
    add_json_arg(parser)
    parser.add_argument("--print-prompt", action="store_true", help="Print the prompt and exit")
    parser.add_argument(
        "--print-command", "--dry-run", dest="print_command", action="store_true",
        help="Print the agent command and exit",
    )
    parser.add_argument(
        "--unsafe-permissions", action="store_true",
        help="Launch the agent without the restricted permission preset",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list_agents:
        print_agents(as_json=args.json)
        return EXIT_OK

    base_dir = args.base_dir.resolve()
    books = list_inbox_books(base_dir)
    prompt = build_prompt(base_dir, books)
    if args.print_prompt:
        print(prompt)
        return EXIT_OK

    choice = resolve_agent_choice(args.agent)
    if choice is None:
        print_install_hints()
        return EXIT_FAILURE
    try:
        agent_argv = build_agent_argv(choice, AGENT_INSTRUCTION, unsafe_permissions=args.unsafe_permissions)
    except UnknownAgentError:
        report_unknown_agent(choice)
        return EXIT_FAILURE

    if args.print_command:
        print(shlex.join(agent_argv))
        return EXIT_OK

    if not books:
        print(f"📭 {INBOX_DIR}/ has no new books (.pdf, .epub, .docx). Nothing to organize.")
        return EXIT_OK

    print(f"📚 {len(books)} new book(s) in {INBOX_DIR}/:")
    for name in books:
        print(f"   - {name}")
    write_prompt_file(base_dir, prompt)
    agent_exit_code = launch_agent(choice, agent_argv, base_dir)
    if agent_exit_code == INTERRUPTED_EXIT_CODE:
        return agent_exit_code
    verify_exit_code = verify_after_agent(base_dir)
    return agent_exit_code or verify_exit_code


if __name__ == "__main__":
    run_main(main)
