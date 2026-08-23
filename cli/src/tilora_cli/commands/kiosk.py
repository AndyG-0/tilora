"""`tilora kiosk enable/disable/status`.

Ports deploy/install.sh::configure_kiosk() and deploy/uninstall.sh's
remove_kiosk_configuration() — same autostart files and Chromium policy
JSON, so `tilora kiosk` is a drop-in alternative to re-running the
installer/uninstaller just to toggle kiosk mode. Points Exec= at the
existing deploy/kiosk.sh rather than duplicating its Chromium flags.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import click

from tilora_cli.paths import InstallPaths, get_paths
from tilora_cli.subprocess_utils import run

AUTOSTART_DESKTOP = Path.home() / ".config" / "autostart" / "tilora-kiosk.desktop"
LABWC_AUTOSTART = Path.home() / ".config" / "labwc" / "autostart"
CHROME_POLICY_DIRS = [
    Path("/etc/chromium/policies/managed"),
    Path("/etc/opt/chrome/policies/managed"),
    Path("/etc/chromium-browser/policies/managed"),
]
POLICY_FILENAME = "tilora.json"
POLICY_CONTENT = (
    '{\n  "AudioCaptureAllowedUrls": '
    '["http://localhost:5173", "http://localhost:3000", '
    '"http://127.0.0.1:5173", "http://127.0.0.1:3000"]\n}\n'
)


@click.group()
def kiosk() -> None:
    """Toggle Chromium kiosk-mode autostart."""


@kiosk.command("status")
@click.pass_context
def kiosk_status(ctx: click.Context) -> None:
    """Show whether kiosk autostart is currently configured."""
    get_paths(ctx)
    if AUTOSTART_DESKTOP.is_file():
        click.secho("enabled", fg="green")
        click.echo(f"  autostart entry: {AUTOSTART_DESKTOP}")
    else:
        click.secho("disabled", fg="yellow")

    policy_present = [d for d in CHROME_POLICY_DIRS if (d / POLICY_FILENAME).is_file()]
    if policy_present:
        click.echo(f"  mic policy: {policy_present[0] / POLICY_FILENAME}")
    else:
        click.echo("  mic policy: not present")


@kiosk.command("enable")
@click.pass_context
def kiosk_enable(ctx: click.Context) -> None:
    """Configure Chromium kiosk-mode autostart (sudo, for the Chromium policy files)."""
    paths: InstallPaths = get_paths(ctx)
    kiosk_script = paths.deploy_dir / "kiosk.sh"
    if not kiosk_script.is_file():
        raise click.ClickException(f"{kiosk_script} not found.")
    kiosk_script.chmod(0o755)

    AUTOSTART_DESKTOP.parent.mkdir(parents=True, exist_ok=True)
    AUTOSTART_DESKTOP.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Tilora Kiosk\n"
        "Comment=Start Tilora smart display in kiosk mode\n"
        f"Exec={kiosk_script}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
    click.echo(f"Wrote {AUTOSTART_DESKTOP}")

    if LABWC_AUTOSTART.parent.is_dir():
        existing = LABWC_AUTOSTART.read_text() if LABWC_AUTOSTART.is_file() else ""
        if str(kiosk_script) not in existing:
            with LABWC_AUTOSTART.open("a") as f:
                f.write(f"\n# Tilora kiosk display\n{kiosk_script} &\n")
            click.echo(f"Updated {LABWC_AUTOSTART}")

    for policy_dir in CHROME_POLICY_DIRS:
        run(["sudo", "mkdir", "-p", str(policy_dir)])
        # Written locally then moved with sudo, since the policy dirs are root-owned.
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
            tmp.write(POLICY_CONTENT)
            tmp_path = Path(tmp.name)
        run(["sudo", "install", "-m", "644", str(tmp_path), str(policy_dir / POLICY_FILENAME)])
        tmp_path.unlink(missing_ok=True)
    click.secho("Kiosk mode enabled.", fg="green")


@kiosk.command("disable")
@click.pass_context
def kiosk_disable(ctx: click.Context) -> None:
    """Remove kiosk-mode autostart and Chromium policy files (sudo)."""
    get_paths(ctx)

    if AUTOSTART_DESKTOP.is_file():
        AUTOSTART_DESKTOP.unlink()
        click.echo(f"Removed {AUTOSTART_DESKTOP}")

    if LABWC_AUTOSTART.is_file():
        remaining = [
            line for line in LABWC_AUTOSTART.read_text().splitlines() if not re.search(r"tilora.*kiosk|kiosk\.sh", line)
        ]
        if any(line.strip() for line in remaining):
            LABWC_AUTOSTART.write_text("\n".join(remaining) + "\n")
        else:
            LABWC_AUTOSTART.unlink()
        click.echo(f"Updated {LABWC_AUTOSTART}")

    for policy_dir in CHROME_POLICY_DIRS:
        policy_file = policy_dir / POLICY_FILENAME
        if policy_file.is_file():
            run(["sudo", "rm", "-f", str(policy_file)])

    click.secho("Kiosk mode disabled.", fg="green")
