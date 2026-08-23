from __future__ import annotations

import click

from tilora_cli.commands.config import config
from tilora_cli.commands.doctor import doctor
from tilora_cli.commands.kiosk import kiosk
from tilora_cli.commands.lifecycle import restart, start, status, stop
from tilora_cli.commands.logs import logs
from tilora_cli.commands.update import update


@click.group()
@click.option(
    "--install-dir",
    envvar="TILORA_INSTALL_DIR",
    default=None,
    help="Path to the Tilora install directory (default: ~/tilora, or $TILORA_INSTALL_DIR).",
)
@click.version_option(package_name="tilora-cli", prog_name="tilora")
@click.pass_context
def cli(ctx: click.Context, install_dir: str | None) -> None:
    """Manage a native (systemd) Tilora installation."""
    ctx.obj = install_dir


cli.add_command(status)
cli.add_command(start)
cli.add_command(stop)
cli.add_command(restart)
cli.add_command(update)
cli.add_command(logs)
cli.add_command(config)
cli.add_command(doctor)
cli.add_command(kiosk)


if __name__ == "__main__":
    cli()
