import json
from pathlib import Path

import pytest

from lib.constants import BACKUP_DIR, DATA_JSON, MAX_DATA_BACKUPS
from lib.json_io import default_backup_dir, load_books, prune_backups, save_books, write_json_atomic


def data_backups(base_dir: Path) -> list[Path]:
    return sorted((base_dir / BACKUP_DIR / "data_json").glob("data.json.*.bak"))


def test_write_json_atomic_creates_file_with_content(tmp_path: Path) -> None:
    target = tmp_path / "data" / "data.json"
    payload = [{"title": "Sách tiếng Việt", "id": "1"}]

    backup_path = write_json_atomic(target, payload)

    assert backup_path is None
    assert json.loads(target.read_text(encoding="utf-8")) == payload
    assert "Sách tiếng Việt" in target.read_text(encoding="utf-8")
    assert not list(target.parent.glob("*.tmp"))


def test_write_json_atomic_backs_up_previous_content(tmp_path: Path) -> None:
    target = tmp_path / "data" / "data.json"
    write_json_atomic(target, [{"id": "old"}])

    backup_path = write_json_atomic(target, [{"id": "new"}])

    assert backup_path is not None
    assert backup_path.parent == tmp_path / BACKUP_DIR / "data_json"
    assert json.loads(backup_path.read_text(encoding="utf-8")) == [{"id": "old"}]
    assert json.loads(target.read_text(encoding="utf-8")) == [{"id": "new"}]


def test_write_json_atomic_without_backup_leaves_no_backup(tmp_path: Path) -> None:
    target = tmp_path / "data" / "data.json"
    write_json_atomic(target, [1])
    write_json_atomic(target, [2], backup=False)

    assert not (tmp_path / BACKUP_DIR).exists()


def test_default_backup_dir_is_repo_level_for_data_files(tmp_path: Path) -> None:
    assert default_backup_dir(tmp_path / "data" / "data.json") == tmp_path / BACKUP_DIR / "data_json"
    assert default_backup_dir(tmp_path / "other.json") == tmp_path / BACKUP_DIR / "other_json"


def test_backups_are_pruned_to_max(tmp_path: Path) -> None:
    for revision in range(MAX_DATA_BACKUPS + 5):
        save_books(tmp_path, [{"revision": revision}])

    backups = data_backups(tmp_path)
    assert len(backups) == MAX_DATA_BACKUPS
    newest = json.loads(backups[-1].read_text(encoding="utf-8"))
    assert newest == [{"revision": MAX_DATA_BACKUPS + 3}]


def test_prune_backups_keeps_newest_by_name(tmp_path: Path) -> None:
    names = [f"data.json.2026010{day}-000000-000000.bak" for day in range(1, 6)]
    for name in names:
        (tmp_path / name).write_text("[]", encoding="utf-8")

    removed = prune_backups(tmp_path, "data.json", keep=2)

    assert sorted(path.name for path in removed) == names[:3]
    assert sorted(path.name for path in tmp_path.iterdir()) == names[3:]


def test_load_books_returns_empty_list_when_missing(tmp_path: Path) -> None:
    assert load_books(tmp_path) == []


@pytest.mark.parametrize("payload", [{"books": []}, "text", 3])
def test_load_books_rejects_non_list(tmp_path: Path, payload: object) -> None:
    data_path = tmp_path / DATA_JSON
    data_path.parent.mkdir(parents=True)
    data_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="JSON array"):
        load_books(tmp_path)
