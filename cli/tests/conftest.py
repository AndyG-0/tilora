from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def fake_install_dir(tmp_path: Path) -> Path:
    install_dir = tmp_path / "tilora"
    (install_dir / "backend" / "config").mkdir(parents=True)
    (install_dir / "frontend").mkdir(parents=True)
    (install_dir / "deploy").mkdir(parents=True)

    (install_dir / "VERSION").write_text("0.14.1\n")
    (install_dir / "backend" / ".env").write_text("AI_MODEL=gpt-4o\n")
    (install_dir / "frontend" / ".env").write_text("PUBLIC_API_BASE_URL=http://localhost:8000\n")
    (install_dir / "backend" / "config" / "dashboard.yaml").write_text("widgets: []\ntabs: []\n")
    (install_dir / "deploy" / "kiosk.sh").write_text("#!/usr/bin/env bash\necho kiosk\n")

    return install_dir
