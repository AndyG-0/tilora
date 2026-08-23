from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

import tilora_cli.commands.kiosk as kiosk_module
from tilora_cli.main import cli


@pytest.fixture(autouse=True)
def isolated_kiosk_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirects the module-level autostart/policy paths under tmp_path.

    Also strips `sudo` from the args real `run()` shells out with, so the
    (now tmp_path-rooted) policy dirs can actually be written in tests
    without root.
    """
    autostart = tmp_path / "home" / ".config" / "autostart" / "tilora-kiosk.desktop"
    labwc = tmp_path / "home" / ".config" / "labwc" / "autostart"
    policy_dirs = [tmp_path / "policy-a", tmp_path / "policy-b"]

    monkeypatch.setattr(kiosk_module, "AUTOSTART_DESKTOP", autostart)
    monkeypatch.setattr(kiosk_module, "LABWC_AUTOSTART", labwc)
    monkeypatch.setattr(kiosk_module, "CHROME_POLICY_DIRS", policy_dirs)

    def fake_run(args: list[str], **kwargs):
        real_args = [a for a in args if a != "sudo"]
        result = subprocess.run(real_args, capture_output=True, text=True, check=False)
        return result

    monkeypatch.setattr(kiosk_module, "run", fake_run)


def test_kiosk_status_disabled_by_default(runner: CliRunner, fake_install_dir: Path) -> None:
    result = runner.invoke(cli, ["--install-dir", str(fake_install_dir), "kiosk", "status"])
    assert result.exit_code == 0
    assert "disabled" in result.output


def test_kiosk_enable_writes_autostart_and_policy(runner: CliRunner, fake_install_dir: Path) -> None:
    result = runner.invoke(cli, ["--install-dir", str(fake_install_dir), "kiosk", "enable"])
    assert result.exit_code == 0, result.output

    assert kiosk_module.AUTOSTART_DESKTOP.is_file()
    assert str(fake_install_dir / "deploy" / "kiosk.sh") in kiosk_module.AUTOSTART_DESKTOP.read_text()
    for policy_dir in kiosk_module.CHROME_POLICY_DIRS:
        assert (policy_dir / kiosk_module.POLICY_FILENAME).is_file()

    status_result = runner.invoke(cli, ["--install-dir", str(fake_install_dir), "kiosk", "status"])
    assert "enabled" in status_result.output


def test_kiosk_disable_removes_autostart_and_policy(runner: CliRunner, fake_install_dir: Path) -> None:
    runner.invoke(cli, ["--install-dir", str(fake_install_dir), "kiosk", "enable"])

    result = runner.invoke(cli, ["--install-dir", str(fake_install_dir), "kiosk", "disable"])

    assert result.exit_code == 0, result.output
    assert not kiosk_module.AUTOSTART_DESKTOP.is_file()
    for policy_dir in kiosk_module.CHROME_POLICY_DIRS:
        assert not (policy_dir / kiosk_module.POLICY_FILENAME).is_file()
