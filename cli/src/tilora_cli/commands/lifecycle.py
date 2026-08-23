from __future__ import annotations

import click

from tilora_cli.constants import SERVICE_UNITS
from tilora_cli.health import is_healthy, wait_for_health
from tilora_cli.paths import get_paths
from tilora_cli.subprocess_utils import run, run_streaming

_STATUS_COLORS = {"active": "green", "failed": "red"}


@click.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show service status, health, and the installed version."""
    paths = get_paths(ctx)
    click.echo(f"Tilora {paths.version}  ({paths.install_dir})")
    click.echo()

    for unit in SERVICE_UNITS:
        active = run(["systemctl", "is-active", unit], check=False).stdout.strip()
        enabled = run(["systemctl", "is-enabled", unit], check=False).stdout.strip()
        color = _STATUS_COLORS.get(active, "yellow")
        click.echo(f"  {unit:<28} " + click.style(active, fg=color) + f"  (enabled: {enabled})")

    click.echo()
    if is_healthy():
        click.secho("  backend health check: ok", fg="green")
    else:
        click.secho("  backend health check: unreachable", fg="red")


@click.command()
@click.pass_context
def start(ctx: click.Context) -> None:
    """Start the Tilora services."""
    get_paths(ctx)
    click.echo("Starting Tilora services (sudo)...")
    if run_streaming(["sudo", "systemctl", "start", *SERVICE_UNITS]) != 0:
        raise click.ClickException("Failed to start services.")
    wait_for_health()


@click.command()
@click.pass_context
def stop(ctx: click.Context) -> None:
    """Stop the Tilora services."""
    get_paths(ctx)
    click.echo("Stopping Tilora services (sudo)...")
    if run_streaming(["sudo", "systemctl", "stop", *SERVICE_UNITS]) != 0:
        raise click.ClickException("Failed to stop services.")


@click.command()
@click.pass_context
def restart(ctx: click.Context) -> None:
    """Restart the Tilora services and wait for the backend to come back up."""
    get_paths(ctx)
    click.echo("Restarting Tilora services (sudo)...")
    if run_streaming(["sudo", "systemctl", "restart", *SERVICE_UNITS]) != 0:
        raise click.ClickException("Failed to restart services.")
    wait_for_health()
