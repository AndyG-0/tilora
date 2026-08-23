"""subprocess.run wrapper shared by every command that shells out.

Mirrors how backend/app/update_check.py runs the same kind of commands
(git/uv/npm/systemctl) — capture output, raise on non-zero, but surface
stderr to the operator instead of swallowing it, since this runs
interactively rather than as a FastAPI background task.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import click


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise click.ClickException(f"`{' '.join(args)}` failed (exit {result.returncode}):\n{result.stderr.strip()}")
    return result


def run_streaming(args: list[str], *, cwd: Path | None = None) -> int:
    """Runs with inherited stdio, for commands whose output should stream live (logs, restart)."""
    return subprocess.run(args, cwd=cwd, check=False).returncode
