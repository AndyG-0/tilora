from __future__ import annotations

from pathlib import Path

import pytest

from tilora_cli.paths import InstallDirNotFoundError, resolve_install_paths


def test_resolves_explicit_install_dir(fake_install_dir: Path) -> None:
    paths = resolve_install_paths(str(fake_install_dir))
    assert paths.install_dir == fake_install_dir.resolve()
    assert paths.backend_dir == fake_install_dir.resolve() / "backend"
    assert paths.version == "0.14.1"


def test_missing_install_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(InstallDirNotFoundError):
        resolve_install_paths(str(tmp_path / "does-not-exist"))


def test_incomplete_install_dir_raises(tmp_path: Path) -> None:
    # Has a VERSION file but no backend/ or deploy/ — not a real checkout.
    (tmp_path / "VERSION").write_text("0.1.0\n")
    with pytest.raises(InstallDirNotFoundError):
        resolve_install_paths(str(tmp_path))


def test_env_var_default(fake_install_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TILORA_INSTALL_DIR", str(fake_install_dir))
    paths = resolve_install_paths(None)
    assert paths.install_dir == fake_install_dir.resolve()
