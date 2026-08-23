"""`tilora doctor` — a battery of PASS/WARN/FAIL checks for a native install.

Mirrors the kind of checks TODO.md's CLI spec calls for (system
requirements, GPU/hwaccel render nodes, port availability, network
connectivity) without needing to run inside the backend's own venv.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import click

from tilora_cli.commands.kiosk import AUTOSTART_DESKTOP, CHROME_POLICY_DIRS, POLICY_FILENAME
from tilora_cli.constants import SERVICE_UNITS
from tilora_cli.health import is_healthy
from tilora_cli.paths import InstallPaths, get_paths
from tilora_cli.subprocess_utils import run

_COLORS = {"PASS": "green", "WARN": "yellow", "FAIL": "red"}
_MIN_FREE_DISK_MB = 500


@dataclass
class CheckResult:
    status: str  # "PASS" | "WARN" | "FAIL"
    message: str


def _check_units() -> CheckResult:
    inactive = [
        unit for unit in SERVICE_UNITS if run(["systemctl", "is-active", unit], check=False).stdout.strip() != "active"
    ]
    if inactive:
        return CheckResult("FAIL", f"not active: {', '.join(inactive)}")
    return CheckResult("PASS", "both services active")


def _check_health() -> CheckResult:
    return CheckResult("PASS", "reachable") if is_healthy() else CheckResult("FAIL", "unreachable")


def _check_disk(paths: InstallPaths) -> CheckResult:
    free_mb = shutil.disk_usage(paths.install_dir).free / (1024 * 1024)
    if free_mb < _MIN_FREE_DISK_MB:
        return CheckResult("WARN", f"{free_mb:.0f} MB free (below {_MIN_FREE_DISK_MB} MB)")
    return CheckResult("PASS", f"{free_mb:.0f} MB free")


def _check_tools() -> CheckResult:
    missing = [tool for tool in ("uv", "node", "npm", "git") if shutil.which(tool) is None]
    if missing:
        return CheckResult("FAIL", f"missing on PATH: {', '.join(missing)}")
    return CheckResult("PASS", "uv, node, npm, git all on PATH")


def _check_hwaccel() -> CheckResult:
    if Path("/dev/dri").is_dir() and any(Path("/dev/dri").glob("renderD*")):
        return CheckResult("PASS", "/dev/dri render node present")
    return CheckResult("WARN", "no /dev/dri render node (hardware transcoding unavailable)")


def _check_git_sync(paths: InstallPaths) -> CheckResult:
    fetch = run(["git", "fetch", "--quiet", "origin"], cwd=paths.install_dir, check=False)
    if fetch.returncode != 0:
        return CheckResult("WARN", "could not reach origin to check for updates")
    behind = run(["git", "rev-list", "--count", "HEAD..@{u}"], cwd=paths.install_dir, check=False).stdout.strip()
    if behind.isdigit() and int(behind) > 0:
        return CheckResult("WARN", f"{behind} commit(s) behind origin — run `tilora update`")
    return CheckResult("PASS", "up to date with origin")


def _check_kiosk_mic_policy(paths: InstallPaths) -> CheckResult:
    if not AUTOSTART_DESKTOP.is_file():
        return CheckResult("PASS", "kiosk not enabled, skipped")

    if any((d / POLICY_FILENAME).is_file() for d in CHROME_POLICY_DIRS):
        return CheckResult("PASS", "Chromium mic policy present")
    return CheckResult("WARN", "kiosk enabled but no Chromium mic policy found — run `tilora kiosk enable`")


@click.command()
@click.pass_context
def doctor(ctx: click.Context) -> None:
    """Run diagnostic checks against the installation."""
    paths = get_paths(ctx)
    checks: list[tuple[str, CheckResult]] = [
        ("systemd services", _check_units()),
        ("backend health", _check_health()),
        ("disk space", _check_disk(paths)),
        ("required tools", _check_tools()),
        ("hwaccel render node", _check_hwaccel()),
        ("git sync", _check_git_sync(paths)),
        ("kiosk mic policy", _check_kiosk_mic_policy(paths)),
    ]

    failed = False
    for name, result in checks:
        color = _COLORS[result.status]
        padded_status = click.style(f"{result.status:<4}", fg=color)
        click.echo(f"  [{padded_status}] {name}: {result.message}")
        if result.status == "FAIL":
            failed = True

    if failed:
        ctx.exit(1)
