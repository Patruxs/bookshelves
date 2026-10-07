from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

ProgressCallback = Callable[[str], None]


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted((to_jsonable(item) for item in value), key=_stable_sort_key)
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value


def _stable_sort_key(item: Any) -> str:
    return json.dumps(item, ensure_ascii=False, sort_keys=True)


def configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        if (getattr(stream, "encoding", None) or "").lower().replace("-", "") == "utf8":
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def emit_json(data: Any) -> None:
    print(json.dumps(to_jsonable(data), ensure_ascii=False, indent=2))


def emit_progress(message: str, *, enabled: bool = True) -> None:
    if not enabled:
        return
    print(message, file=sys.stderr, flush=True)


def make_progress_printer(*, enabled: bool) -> ProgressCallback | None:
    if not enabled:
        return None
    return lambda message: emit_progress(message, enabled=True)

