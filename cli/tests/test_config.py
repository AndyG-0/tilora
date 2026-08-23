from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from tilora_cli.main import cli


def test_get_existing_env_key(runner: CliRunner, fake_install_dir: Path) -> None:
    result = runner.invoke(cli, ["--install-dir", str(fake_install_dir), "config", "get", "AI_MODEL"])
    assert result.exit_code == 0
    assert result.output.strip() == "gpt-4o"


def test_get_missing_env_key_fails(runner: CliRunner, fake_install_dir: Path) -> None:
    result = runner.invoke(cli, ["--install-dir", str(fake_install_dir), "config", "get", "NOPE"])
    assert result.exit_code != 0


def test_set_new_env_key_then_get(runner: CliRunner, fake_install_dir: Path) -> None:
    set_result = runner.invoke(cli, ["--install-dir", str(fake_install_dir), "config", "set", "FOO", "bar"])
    assert set_result.exit_code == 0

    get_result = runner.invoke(cli, ["--install-dir", str(fake_install_dir), "config", "get", "FOO"])
    assert get_result.output.strip() == "bar"


def test_set_overwrites_existing_env_key(runner: CliRunner, fake_install_dir: Path) -> None:
    runner.invoke(cli, ["--install-dir", str(fake_install_dir), "config", "set", "AI_MODEL", "claude-sonnet-5"])
    get_result = runner.invoke(cli, ["--install-dir", str(fake_install_dir), "config", "get", "AI_MODEL"])
    assert get_result.output.strip() == "claude-sonnet-5"


def test_frontend_env_target(runner: CliRunner, fake_install_dir: Path) -> None:
    result = runner.invoke(
        cli,
        [
            "--install-dir",
            str(fake_install_dir),
            "config",
            "get",
            "PUBLIC_API_BASE_URL",
            "--file",
            "frontend-env",
        ],
    )
    assert result.output.strip() == "http://localhost:8000"


def test_dashboard_set_and_get(runner: CliRunner, fake_install_dir: Path) -> None:
    set_result = runner.invoke(
        cli,
        [
            "--install-dir",
            str(fake_install_dir),
            "config",
            "set",
            "timezone",
            '"America/Chicago"',
            "--file",
            "dashboard",
        ],
    )
    assert set_result.exit_code == 0, set_result.output

    get_result = runner.invoke(
        cli, ["--install-dir", str(fake_install_dir), "config", "get", "timezone", "--file", "dashboard"]
    )
    assert "America/Chicago" in get_result.output
