from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import NamedTuple

from .cli_common import add_base_dir_arg, add_json_arg, add_mode_args, confirm, json_mode
from .constants import INBOX_DIR
from .output import ProgressCallback, emit_json


class InboxSelectionError(ValueError):
    pass


@dataclass(frozen=True)
class InboxJob:
    title: str
    source_suffix: str
    target_suffix: str
    action: str
    execute_hint: str


@dataclass
class ConversionPlan:
    source: Path
    target: Path
    status: str
    message: str


@dataclass
class ConversionResult:
    source: str
    target: str
    status: str
    message: str
    backup_path: str | None = None

    def as_dict(self) -> dict[str, str]:
        return {key: value for key, value in asdict(self).items() if value is not None}


class Outcome(NamedTuple):
    status: str
    message: str
    backup_path: Path | None = None


ConvertOne = Callable[[ConversionPlan], tuple[str, str] | Outcome]


def format_label(suffix: str) -> str:
    return suffix.lstrip(".").upper()


def add_inbox_args(parser: argparse.ArgumentParser, *, execute_help: str) -> None:
    add_base_dir_arg(parser)
    parser.add_argument("--inbox-dir", default=INBOX_DIR, help="Inbox directory under base-dir")
    add_mode_args(parser, execute_help=execute_help)
    parser.add_argument("--fail-fast", action="store_true", help="Stop after the first failure")
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        dest="files",
        metavar="NAME",
        help="Process only the Inbox file with this name or stem (a unique substring also works). Repeatable.",
    )
    add_json_arg(parser)


def relative_path(path: Path, base_dir: Path) -> str:
    try:
        return path.relative_to(base_dir).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_inbox_dir(base_dir: Path, inbox_arg: str) -> Path:
    inbox_dir = Path(inbox_arg)
    if not inbox_dir.is_absolute():
        inbox_dir = base_dir / inbox_dir

    inbox_dir = inbox_dir.resolve()
    if not inbox_dir.is_relative_to(base_dir):
        raise ValueError(f"--inbox-dir must be inside --base-dir: {inbox_dir}")
    if not inbox_dir.exists():
        raise FileNotFoundError(f"Inbox directory not found: {inbox_dir}")
    if not inbox_dir.is_dir():
        raise NotADirectoryError(f"Inbox path is not a directory: {inbox_dir}")
    return inbox_dir


def match_inbox_file(candidates: list[Path], pattern: str, suffix: str) -> list[Path]:
    needle = Path(pattern.strip()).name.casefold()
    exact = [path for path in candidates if needle in (path.name.casefold(), path.stem.casefold())]
    if exact:
        return exact
    partial = [path for path in candidates if needle in path.name.casefold()]
    if not partial:
        raise FileNotFoundError(f"No {format_label(suffix)} in Inbox matches --file {pattern!r}")
    if len(partial) > 1:
        names = "\n".join(f"  - {path.name}" for path in partial)
        raise InboxSelectionError(
            f"--file {pattern!r} matches {len(partial)} {format_label(suffix)} files; use an exact name:\n{names}"
        )
    return partial


def select_sources(inbox_dir: Path, suffix: str, files: list[str] | None = None) -> list[Path]:
    candidates = sorted(
        path for path in inbox_dir.iterdir() if path.is_file() and path.suffix.lower() == suffix
    )
    if not files:
        return candidates

    selected: list[Path] = []
    for pattern in files:
        if not pattern.strip():
            continue
        matches = match_inbox_file(candidates, pattern, suffix)
        selected.extend(path for path in matches if path not in selected)
    return selected


def build_plan(
    inbox_dir: Path,
    job: InboxJob,
    *,
    overwrite: bool,
    files: list[str] | None = None,
) -> list[ConversionPlan]:
    target_label = format_label(job.target_suffix)
    plans: list[ConversionPlan] = []
    for source in select_sources(inbox_dir, job.source_suffix, files):
        target = source.with_suffix(job.target_suffix)
        if not target.exists():
            plans.append(ConversionPlan(source, target, "planned", job.action))
        elif overwrite:
            message = f"{job.action} and overwrite existing {target_label}"
            plans.append(ConversionPlan(source, target, "planned", message))
        else:
            message = f"{target_label} already exists; use --overwrite to replace it"
            plans.append(ConversionPlan(source, target, "skipped", message))
    return plans


def plan_to_results(plans: list[ConversionPlan], base_dir: Path) -> list[ConversionResult]:
    return [_result(plan, base_dir, Outcome(plan.status, plan.message)) for plan in plans]


def run_plan(
    plans: list[ConversionPlan],
    base_dir: Path,
    convert_one: ConvertOne,
    *,
    progress: ProgressCallback | None = None,
    fail_fast: bool = False,
    start_message: str | None = None,
) -> list[ConversionResult]:
    report = progress or (lambda _message: None)
    total = len(plans)
    if total:
        report(start_message or f"Converting {total} book(s)...")

    results: list[ConversionResult] = []
    for index, plan in enumerate(plans, 1):
        prefix = f"[{index}/{total}]"
        if plan.status == "skipped":
            report(f"{prefix} skip {plan.source.name} - {plan.message}")
            results.append(_result(plan, base_dir, Outcome(plan.status, plan.message)))
            continue

        report(f"{prefix} converting {plan.source.name} -> {plan.target.name}")
        try:
            outcome = Outcome(*convert_one(plan))
        except Exception as exc:
            outcome = Outcome("failed", f"{type(exc).__name__}: {exc}")
        report(f"{prefix} done: {outcome.status} - {outcome.message}")
        results.append(_result(plan, base_dir, outcome))
        if fail_fast and outcome.status == "failed":
            break

    if total:
        report("Done.")
    return results


def _result(plan: ConversionPlan, base_dir: Path, outcome: Outcome) -> ConversionResult:
    backup = relative_path(outcome.backup_path, base_dir) if outcome.backup_path else None
    return ConversionResult(
        source=relative_path(plan.source, base_dir),
        target=relative_path(plan.target, base_dir),
        status=outcome.status,
        message=outcome.message,
        backup_path=backup,
    )


def print_summary(
    results: list[ConversionResult],
    job: InboxJob,
    *,
    dry_run: bool,
    header_lines: tuple[str, ...] = (),
) -> None:
    print("=" * 60)
    print(job.title)
    print("=" * 60)
    print(f"Mode: {'dry-run' if dry_run else 'execute'}")
    for line in header_lines:
        print(line)
    print()

    if not results:
        print(f"No {format_label(job.source_suffix)} files found.")
        return

    for result in results:
        location = result.source if result.source == result.target else f"{result.source} -> {result.target}"
        print(f"- [{result.status}] {location}")
        print(f"  {result.message}")
        if result.backup_path:
            print(f"  backup: {result.backup_path}")

    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1

    print()
    print("Summary:")
    for status in sorted(counts):
        print(f"- {status}: {counts[status]}")

    if dry_run:
        print()
        print(f"No files changed. {job.execute_hint}")
        print('Tip: process one book with --execute --file "Book Name"')


def report_cancelled(*, as_json: bool) -> None:
    if as_json:
        emit_json({"ok": False, "cancelled": True})
    else:
        print("Cancelled. No files changed.", file=sys.stderr)


def confirm_execution(plans: list[ConversionPlan], question: str, *, assume_yes: bool, as_json: bool) -> bool:
    if not any(plan.status == "planned" for plan in plans):
        return True
    with json_mode(as_json):
        confirmed = confirm(question, assume_yes=assume_yes)
    if not confirmed:
        report_cancelled(as_json=as_json)
    return confirmed


def report_error(exc: BaseException, *, as_json: bool) -> None:
    if as_json:
        emit_json({"ok": False, "error": str(exc)})
    else:
        print(f"ERROR: {exc}", file=sys.stderr)


def finish(
    results: list[ConversionResult],
    job: InboxJob,
    *,
    dry_run: bool,
    as_json: bool,
    extra: dict[str, str] | None = None,
) -> int:
    ok = all(result.status != "failed" for result in results)
    if as_json:
        emit_json(
            {
                "ok": ok,
                "dry_run": dry_run,
                **(extra or {}),
                "results": [result.as_dict() for result in results],
            }
        )
    else:
        header_lines = tuple(f"{key.replace('_', ' ').capitalize()}: {value}" for key, value in (extra or {}).items())
        print_summary(results, job, dry_run=dry_run, header_lines=header_lines)
    return 0 if ok else 1
