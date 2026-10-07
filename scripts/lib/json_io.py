from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .constants import BACKUP_DIR, DATA_JSON, MAX_DATA_BACKUPS

DATA_DIR_NAME = Path(DATA_JSON).parent.name
NEW_FILE_MODE = 0o644

Book = dict[str, Any]


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def load_books(base_dir: Path) -> list[Book]:
    data = load_json(base_dir / DATA_JSON, default=[])
    if not isinstance(data, list):
        raise ValueError(f"{DATA_JSON} must contain a JSON array, got {type(data).__name__}")
    return data


def backup_dir_for(base_dir: Path, path: Path) -> Path:
    return base_dir / BACKUP_DIR / path.name.replace(".", "_")


def default_backup_dir(path: Path) -> Path:
    repo_root = path.parent.parent if path.parent.name == DATA_DIR_NAME else path.parent
    return backup_dir_for(repo_root, path)


def backup_file(path: Path, backup_dir: Path, *, keep: int = MAX_DATA_BACKUPS) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_path = backup_dir / f"{path.name}.{stamp}.bak"
    shutil.copy2(path, backup_path)
    prune_backups(backup_dir, path.name, keep=keep)
    return backup_path


def prune_backups(backup_dir: Path, file_name: str, *, keep: int = MAX_DATA_BACKUPS) -> list[Path]:
    backups = sorted(backup_dir.glob(f"{file_name}.*.bak"), key=lambda backup: backup.name, reverse=True)
    removed = backups[keep:]
    for old_backup in removed:
        old_backup.unlink(missing_ok=True)
    return removed


def write_json_atomic(
    path: Path,
    data: Any,
    *,
    backup: bool = True,
    backup_dir: Path | None = None,
) -> Path | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = None

    if backup and path.exists():
        backup_path = backup_file(path, backup_dir or default_backup_dir(path))

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            shutil.copymode(path, tmp_path)
        else:
            tmp_path.chmod(NEW_FILE_MODE)
        os.replace(tmp_path, path)
        tmp_path = None
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
    return backup_path


def save_books(base_dir: Path, books: list[Book], *, backup: bool = True) -> Path | None:
    data_path = base_dir / DATA_JSON
    return write_json_atomic(data_path, books, backup=backup, backup_dir=backup_dir_for(base_dir, data_path))
