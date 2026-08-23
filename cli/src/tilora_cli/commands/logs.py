from __future__ import annotations

import click

from tilora_cli.constants import BACKEND_UNIT, FRONTEND_UNIT
from tilora_cli.paths import get_paths
from tilora_cli.subprocess_utils import run_streaming


@click.command()
@click.option("-f", "--follow", is_flag=True, help="Follow the log output (like tail -f).")
@click.option("-n", "--lines", default=100, show_default=True, help="Number of recent lines to show.")
@click.option("--backend", "backend_only", is_flag=True, help="Show only the backend service's logs.")
@click.option("--frontend", "frontend_only", is_flag=True, help="Show only the frontend service's logs.")
@click.pass_context
def logs(ctx: click.Context, follow: bool, lines: int, backend_only: bool, frontend_only: bool) -> None:
    """Stream or tail the Tilora service logs (journalctl)."""
    get_paths(ctx)
    if backend_only and frontend_only:
        raise click.UsageError("Pass at most one of --backend / --frontend.")

    units = [BACKEND_UNIT] if backend_only else [FRONTEND_UNIT] if frontend_only else [BACKEND_UNIT, FRONTEND_UNIT]

    args = ["journalctl", "-n", str(lines)]
    for unit in units:
        args += ["-u", unit]
    if follow:
        args.append("-f")

    run_streaming(args)
