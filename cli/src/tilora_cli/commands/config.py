"""`tilora config get/set` for backend/.env, frontend/.env, and dashboard.yaml.

dashboard.yaml is read/written with plain pyyaml, not the schema
validator in backend/app/config.py — that module lives in the backend's
own venv and isn't reachable from this package's isolated `uv tool`
environment, and full validation is out of scope for a get/set surface.
"""

from __future__ import annotations

from pathlib import Path

import click
import yaml

from tilora_cli.env_file import get_env_value, set_env_value
from tilora_cli.paths import InstallPaths, get_paths

_TARGETS = ["backend-env", "frontend-env", "dashboard"]


def _env_path(paths: InstallPaths, target: str) -> Path:
    return paths.backend_dir / ".env" if target == "backend-env" else paths.frontend_dir / ".env"


def _dashboard_path(paths: InstallPaths) -> Path:
    return paths.backend_dir / "config" / "dashboard.yaml"


def _load_dashboard(paths: InstallPaths) -> dict:
    path = _dashboard_path(paths)
    if not path.is_file():
        raise click.ClickException(f"{path} not found.")
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise click.ClickException(f"{path} does not contain a YAML mapping at the top level.")
    return data


@click.group()
def config() -> None:
    """Get or set values in backend/.env, frontend/.env, or dashboard.yaml."""


@config.command("get")
@click.argument("key")
@click.option("--file", "target", type=click.Choice(_TARGETS), default="backend-env", show_default=True)
@click.pass_context
def config_get(ctx: click.Context, key: str, target: str) -> None:
    """Print the value of KEY."""
    paths = get_paths(ctx)
    if target == "dashboard":
        data = _load_dashboard(paths)
        if key not in data:
            raise click.ClickException(f"'{key}' not found in {_dashboard_path(paths)}")
        click.echo(yaml.safe_dump({key: data[key]}, sort_keys=False).strip())
        return

    value = get_env_value(_env_path(paths, target), key)
    if value is None:
        raise click.ClickException(f"'{key}' not set in {_env_path(paths, target)}")
    click.echo(value)


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.option("--file", "target", type=click.Choice(_TARGETS), default="backend-env", show_default=True)
@click.pass_context
def config_set(ctx: click.Context, key: str, value: str, target: str) -> None:
    """Set KEY to VALUE."""
    paths = get_paths(ctx)
    if target == "dashboard":
        data = _load_dashboard(paths)
        data[key] = yaml.safe_load(value)
        _dashboard_path(paths).write_text(yaml.safe_dump(data, sort_keys=False))
        click.secho(f"Set {key} in {_dashboard_path(paths)}", fg="green")
        return

    file_path = _env_path(paths, target)
    set_env_value(file_path, key, value)
    click.secho(f"Set {key} in {file_path}", fg="green")
