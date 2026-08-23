from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from tilora_cli.main import cli


def _fake_completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def test_status_reports_active_and_healthy(
    runner: CliRunner, fake_install_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "tilora_cli.commands.lifecycle.run",
        lambda args, **kwargs: _fake_completed("active" if "is-active" in args else "enabled"),
    )
    monkeypatch.setattr("tilora_cli.commands.lifecycle.is_healthy", lambda: True)

    result = runner.invoke(cli, ["--install-dir", str(fake_install_dir), "status"])

    assert result.exit_code == 0
    assert "0.14.1" in result.output
    assert "active" in result.output
    assert "ok" in result.output


def test_status_reports_unhealthy(runner: CliRunner, fake_install_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tilora_cli.commands.lifecycle.run", lambda args, **kwargs: _fake_completed("inactive"))
    monkeypatch.setattr("tilora_cli.commands.lifecycle.is_healthy", lambda: False)

    result = runner.invoke(cli, ["--install-dir", str(fake_install_dir), "status"])

    assert result.exit_code == 0
    assert "unreachable" in result.output


def test_start_fails_cleanly_when_systemctl_fails(
    runner: CliRunner, fake_install_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("tilora_cli.commands.lifecycle.run_streaming", lambda args, **kwargs: 1)

    result = runner.invoke(cli, ["--install-dir", str(fake_install_dir), "start"])

    assert result.exit_code != 0
    assert "Failed to start" in result.output


def test_restart_waits_for_health(runner: CliRunner, fake_install_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tilora_cli.commands.lifecycle.run_streaming", lambda args, **kwargs: 0)
    waited = {"called": False}

    def fake_wait_for_health() -> None:
        waited["called"] = True

    monkeypatch.setattr("tilora_cli.commands.lifecycle.wait_for_health", fake_wait_for_health)

    result = runner.invoke(cli, ["--install-dir", str(fake_install_dir), "restart"])

    assert result.exit_code == 0
    assert waited["called"]


def test_help_does_not_require_install_dir(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["status", "--help"])
    assert result.exit_code == 0
