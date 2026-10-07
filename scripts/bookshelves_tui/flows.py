from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from bookshelves_tui.library import list_inbox_files
from bookshelves_tui.modals import ConfirmModal, DangerConfirmModal, SelectModal
from bookshelves_tui.runner import NOT_RUN, PERFORM_ARGS, build_argv, subprocess_env
from lib.constants import INBOX_DIR

if TYPE_CHECKING:
    from bookshelves_tui.app import BookshelvesApp

AUTO_PICK = ""


@dataclass(frozen=True)
class DoctorReport:
    errors: int
    warnings: int
    failed: bool

    @property
    def status(self) -> str:
        return "FAILED" if self.failed else "OK"


def runner_is_free(app: BookshelvesApp) -> bool:
    if app.runner.busy:
        app.notify("A command is already running.", severity="warning")
        return False
    return True


async def confirmed(app: BookshelvesApp, question: str) -> bool:
    result = await app.push_screen_wait(ConfirmModal(question))
    return result.ok


async def danger_confirmed(app: BookshelvesApp, question: str) -> bool:
    result = await app.push_screen_wait(DangerConfirmModal(question))
    return result.ok


async def run_generate(app: BookshelvesApp) -> int | None:
    if not runner_is_free(app):
        return None
    if not await confirmed(app, "Regenerate data.json and extract missing covers from Books/?"):
        return None
    return await app.runner.run("generate", app.runner.base_dir_args)


async def run_generate_force_covers(app: BookshelvesApp) -> int | None:
    if not runner_is_free(app):
        return None
    if not await confirmed(app, "Regenerate data.json and force-rebuild every cover image?"):
        return None
    return await app.runner.run("generate", [*app.runner.base_dir_args, "--force"])


async def run_upload_dry_run(app: BookshelvesApp) -> int:
    return await app.runner.run("upload", [*app.runner.base_dir_args, "--dry-run"])


async def upload_after_dry_run(app: BookshelvesApp, upload_flags: list[str], question: str,
                               danger: bool = False) -> int | None:
    if not runner_is_free(app):
        return None
    upload_args = [*app.runner.base_dir_args, *upload_flags]
    dry_run_exit_code = await app.runner.run("upload", [*upload_args, "--dry-run"])
    if dry_run_exit_code != 0:
        app.notify(f"Dry run failed (exit {dry_run_exit_code}); nothing was uploaded.", severity="error")
        return dry_run_exit_code
    approved = await danger_confirmed(app, question) if danger else await confirmed(app, question)
    if not approved:
        return None
    return await app.runner.run("upload", [*upload_args, *PERFORM_ARGS])


async def run_upload_new_books(app: BookshelvesApp) -> int | None:
    return await upload_after_dry_run(app, [], "Upload the new books listed above?")


async def run_force_reupload_all(app: BookshelvesApp) -> int | None:
    return await upload_after_dry_run(
        app, ["--force"], "Re-upload ALL books, overwriting every existing release asset?", danger=True,
    )


async def run_hard_reset_release(app: BookshelvesApp) -> int | None:
    return await upload_after_dry_run(
        app, ["--hard-reset"], "DELETE the release entirely, recreate it and re-upload ALL books?", danger=True,
    )


async def run_structure_log(app: BookshelvesApp) -> int:
    return await app.runner.run("structure", app.runner.base_dir_args)


def parse_doctor_report(doctor_json: str, exit_code: int) -> DoctorReport:
    result = json.loads(doctor_json)
    return DoctorReport(errors=len(result["errors"]), warnings=len(result["warnings"]), failed=exit_code != 0)


async def read_doctor_report(app: BookshelvesApp) -> DoctorReport | None:
    argv = build_argv("doctor", [*app.runner.base_dir_args, "--json", "--strict"])
    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(app.base_dir),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=subprocess_env(),
        )
        stdout, _ = await process.communicate()
        return parse_doctor_report(stdout.decode("utf-8", errors="replace"), process.returncode or 0)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        app.notify(f"Could not read doctor --json: {exc}", severity="error")
        return None


async def run_doctor(app: BookshelvesApp) -> int:
    exit_code = await app.runner.run("doctor", [*app.runner.base_dir_args, "--strict"])
    if exit_code == NOT_RUN:
        return exit_code
    report = await read_doctor_report(app)
    if report is not None:
        app.last_doctor_report = report
        app.reload_sections()
    return exit_code


def parse_installed_agents(list_agents_json: str) -> list[str]:
    report = json.loads(list_agents_json)
    return [str(agent["name"]) for agent in report["agents"] if agent.get("installed")]


async def read_installed_agents(app: BookshelvesApp) -> list[str] | None:
    try:
        process = await asyncio.create_subprocess_exec(
            *build_argv("auto-organize", ["--list-agents", "--json", *app.runner.base_dir_args]),
            cwd=str(app.base_dir),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=subprocess_env(),
        )
    except OSError as exc:
        app.notify(f"Cannot list agents: {exc}", severity="error")
        return None
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        app.notify(stderr.decode("utf-8", errors="replace").strip() or "auto-organize --list-agents failed.",
                   severity="error")
        return None
    try:
        return parse_installed_agents(stdout.decode("utf-8", errors="replace"))
    except (ValueError, KeyError, TypeError) as exc:
        app.notify(f"Cannot read auto-organize --list-agents --json: {exc}", severity="error")
        return None


async def run_auto_organize(app: BookshelvesApp) -> int | None:
    if not list_inbox_files(app.base_dir):
        app.notify(f"{INBOX_DIR}/ is empty; nothing to organize.", severity="warning")
        return None
    if not runner_is_free(app):
        return None
    installed_agents = await read_installed_agents(app)
    if installed_agents is None:
        return None
    agent_options = [("Auto-pick", AUTO_PICK), *((agent, agent) for agent in installed_agents)]
    chosen_agent = await app.push_screen_wait(SelectModal("Auto-Organize with which agent?", agent_options))
    if chosen_agent is None:
        return None
    agent_label = chosen_agent or "the first installed agent"
    if not await confirmed(app, f"Launch Auto-Organize with {agent_label}? The agent takes over the terminal."):
        return None
    agent_args = ["--agent", chosen_agent] if chosen_agent else []
    return app.runner.run_interactive("auto-organize", [*app.runner.base_dir_args, *agent_args])


async def run_unlock_pdfs(app: BookshelvesApp) -> int | None:
    return await app.runner.preview_then_execute(
        "unlock-pdfs", app.runner.base_dir_args, f"Execute PDF unlock for {INBOX_DIR}/?",
    )


async def run_epub_to_pdf(app: BookshelvesApp) -> int | None:
    return await app.runner.preview_then_execute(
        "epub-to-pdf", app.runner.base_dir_args, f"Convert EPUB files in {INBOX_DIR}/ to PDF?",
        checkbox="Overwrite existing PDFs", checked_args=["--overwrite"],
    )


async def run_pdf_to_epub(app: BookshelvesApp) -> int | None:
    return await app.runner.preview_then_execute(
        "pdf-to-epub", app.runner.base_dir_args, f"Convert PDF files in {INBOX_DIR}/ to EPUB?",
        checkbox="Overwrite existing EPUBs", checked_args=["--overwrite"],
    )


async def run_rename_files(app: BookshelvesApp) -> int | None:
    return await app.runner.preview_then_execute(
        "rename", app.runner.base_dir_args, "Execute the rename?",
    )
