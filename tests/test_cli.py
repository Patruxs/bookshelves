import pytest

import cli
from conftest import run_cli


@pytest.mark.parametrize(
    ("alias", "command"),
    [("validate", "doctor"), ("unlock", "unlock-pdfs"), ("epub2pdf", "epub-to-pdf"), ("organize", "auto-organize")],
)
def test_aliases_normalize(alias: str, command: str) -> None:
    assert cli.normalize_command(alias) == command


def test_every_alias_targets_a_known_command() -> None:
    assert set(cli.ALIASES.values()) <= set(cli.COMMANDS)


def test_known_command_normalizes_to_itself() -> None:
    assert cli.normalize_command("generate") == "generate"


def test_suggest_commands_finds_close_names() -> None:
    assert cli.suggest_commands("genrate")[0] == "generate"
    assert "doctor" in cli.suggest_commands("doctr")
    assert cli.suggest_commands("zzzzzz") == []


def test_unknown_command_fails_with_suggestion() -> None:
    result = run_cli("genrate")

    assert result.returncode != 0
    assert result.returncode in (1, 2)
    assert "generate" in result.stderr
    assert result.stdout == ""


@pytest.mark.parametrize("flag", ["--help", "-h", "help"])
def test_help_exits_zero(flag: str) -> None:
    result = run_cli(flag)

    assert result.returncode == 0
    for command in cli.COMMANDS:
        assert command in result.stdout


def test_alias_dispatches_to_command() -> None:
    result = run_cli("validate", "--help")

    assert result.returncode == 0
    assert "--base-dir" in result.stdout
