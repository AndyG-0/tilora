"""`tilora update` — native-install fast-forward update.

Ports the exact sequence deploy/update.sh and
backend/app/update_check.py::run_update() already perform: fetch + fast-
forward merge, `uv sync` the backend, rebuild the frontend, restart via
systemctl, then wait for the health check. Kept as a standalone,
synchronous command (rather than calling into the backend) since it needs
to work even when the backend is down or mid-upgrade.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import click

from tilora_cli.constants import SERVICE_UNITS
from tilora_cli.health import wait_for_health
from tilora_cli.paths import get_paths
from tilora_cli.subprocess_utils import run, run_streaming


def _resolve_uv_binary() -> str:
    found = shutil.which("uv")
    if found:
        return found
    local_uv = Path.home() / ".local" / "bin" / "uv"
    if local_uv.is_file():
        return str(local_uv)
    raise click.ClickException("`uv` not found on PATH or in ~/.local/bin. Install it first: https://astral.sh/uv")


@click.command()
@click.option(
    "--ref",
    "repository_ref",
    envvar="TILORA_REPOSITORY_REF",
    default="main",
    show_default=True,
    help="Git ref to fast-forward to.",
)
@click.pass_context
def update(ctx: click.Context, repository_ref: str) -> None:
    """Fast-forward, rebuild, and restart a native installation."""
    if os.geteuid() == 0:
        raise click.ClickException("Run this as the non-root account that owns the Tilora installation.")

    paths = get_paths(ctx)
    uv_bin = _resolve_uv_binary()

    click.echo(f"Fetching {repository_ref}...")
    run(["git", "fetch", "--quiet", "origin", repository_ref], cwd=paths.install_dir)
    run(["git", "merge", "--ff-only", f"origin/{repository_ref}"], cwd=paths.install_dir)

    click.echo("Installing backend dependencies...")
    run([uv_bin, "sync"], cwd=paths.backend_dir)

    click.echo("Building frontend...")
    run(["npm", "ci"], cwd=paths.frontend_dir)
    run(["npm", "run", "build"], cwd=paths.frontend_dir)

    click.echo("Restarting services (sudo)...")
    if run_streaming(["sudo", "systemctl", "restart", *SERVICE_UNITS]) != 0:
        raise click.ClickException("Failed to restart services.")

    wait_for_health()

    new_paths = get_paths(ctx)
    click.secho(f"Updated to v{new_paths.version}.", fg="green")
