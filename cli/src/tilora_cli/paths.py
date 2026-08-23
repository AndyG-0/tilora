"""Locates the Tilora install directory a running command should act on.

Mirrors the env var name and default layout deploy/install.sh already
uses (TILORA_INSTALL_DIR, ~/tilora), so the CLI agrees with the installer
and the in-app updater (backend/app/update_check.py) about where things
live without importing backend code into this package's own venv.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import click


class InstallDirNotFoundError(click.ClickException):
    def __init__(self, install_dir: Path):
        super().__init__(
            f"{install_dir} does not look like a Tilora installation "
            "(missing VERSION, backend/, or deploy/). Pass --install-dir, "
            "set TILORA_INSTALL_DIR, or run deploy/install.sh first."
        )


@dataclass(frozen=True)
class InstallPaths:
    install_dir: Path
    backend_dir: Path
    frontend_dir: Path
    deploy_dir: Path
    version_file: Path

    @property
    def version(self) -> str:
        try:
            return self.version_file.read_text().strip()
        except OSError:
            return "unknown"


def resolve_install_paths(install_dir: str | None) -> InstallPaths:
    candidate = Path(install_dir).expanduser() if install_dir else _default_install_dir()
    candidate = candidate.resolve()

    paths = InstallPaths(
        install_dir=candidate,
        backend_dir=candidate / "backend",
        frontend_dir=candidate / "frontend",
        deploy_dir=candidate / "deploy",
        version_file=candidate / "VERSION",
    )

    if not (paths.version_file.is_file() and paths.backend_dir.is_dir() and paths.deploy_dir.is_dir()):
        raise InstallDirNotFoundError(candidate)

    return paths


def _default_install_dir() -> Path:
    env_dir = os.environ.get("TILORA_INSTALL_DIR")
    if env_dir:
        return Path(env_dir).expanduser()
    return Path.home() / "tilora"


def get_paths(ctx: click.Context) -> InstallPaths:
    """Resolves install paths from the top-level --install-dir option.

    Deferred until a command actually needs it (rather than resolved once
    in the group callback) so `tilora <subcommand> --help` works from
    anywhere, without requiring a real install directory to exist.
    """
    return resolve_install_paths(ctx.obj)
