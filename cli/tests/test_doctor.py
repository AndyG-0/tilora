from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from tilora_cli.commands.doctor import CheckResult
from tilora_cli.main import cli


def _stub_all_checks(monkeypatch: pytest.MonkeyPatch, status: str) -> None:
    result = CheckResult(status, "stubbed")
    for name in (
        "_check_units",
        "_check_health",
        "_check_tools",
        "_check_hwaccel",
    ):
        monkeypatch.setattr(f"tilora_cli.commands.doctor.{name}", lambda *a, **k: result)
    for name in ("_check_disk", "_check_git_sync", "_check_kiosk_mic_policy"):
        monkeypatch.setattr(f"tilora_cli.commands.doctor.{name}", lambda paths, r=result: r)


def test_doctor_exits_zero_when_all_pass(
    runner: CliRunner, fake_install_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_all_checks(monkeypatch, "PASS")

    result = runner.invoke(cli, ["--install-dir", str(fake_install_dir), "doctor"])

    assert result.exit_code == 0
    assert "PASS" in result.output


def test_doctor_exits_nonzero_when_any_fails(
    runner: CliRunner, fake_install_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_all_checks(monkeypatch, "PASS")
    monkeypatch.setattr("tilora_cli.commands.doctor._check_health", lambda *a, **k: CheckResult("FAIL", "unreachable"))

    result = runner.invoke(cli, ["--install-dir", str(fake_install_dir), "doctor"])

    assert result.exit_code == 1
