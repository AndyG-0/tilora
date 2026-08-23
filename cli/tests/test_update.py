from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from tilora_cli.main import cli


def _ok(*_args, **_kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")


def test_update_runs_full_sequence(runner: CliRunner, fake_install_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("os.geteuid", lambda: 1000, raising=False)
    monkeypatch.setattr("tilora_cli.commands.update._resolve_uv_binary", lambda: "uv")
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs):
        calls.append(args)
        return _ok()

    monkeypatch.setattr("tilora_cli.commands.update.run", fake_run)
    monkeypatch.setattr("tilora_cli.commands.update.run_streaming", lambda args, **kwargs: 0)
    monkeypatch.setattr("tilora_cli.commands.update.wait_for_health", lambda: None)

    result = runner.invoke(cli, ["--install-dir", str(fake_install_dir), "update"])

    assert result.exit_code == 0, result.output
    assert any("git" in c and "fetch" in c for c in calls)
    assert any("git" in c and "merge" in c for c in calls)
    assert any("uv" in c and "sync" in c for c in calls)
    assert any("npm" in c and "ci" in c for c in calls)
    assert "Updated to v0.14.1" in result.output


def test_update_refuses_to_run_as_root(
    runner: CliRunner, fake_install_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("os.geteuid", lambda: 0, raising=False)

    result = runner.invoke(cli, ["--install-dir", str(fake_install_dir), "update"])

    assert result.exit_code != 0
    assert "non-root" in result.output
