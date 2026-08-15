"""Checks GitHub releases for newer versions of the project.

Surfaces a simple "an update is available" signal to the UI
(`app.api.version`) — no auto-update, just notification. See `VERSION` at
the repo root for the current version and the project README for the
release-tagging convention (`vX.Y.Z`).

For native (systemd) installs the backend can also perform an in-place
update via `run_update()`, triggered through `app.api.system`.  It pulls
the latest code, rebuilds both services, and then execs a sudoers-granted
restart wrapper that brings everything back up.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from typing import Any

import httpx

from app.config import BACKEND_ROOT, settings

logger = logging.getLogger(__name__)

VERSION_PATH = BACKEND_ROOT.parent / "VERSION"

CURRENT_VERSION = VERSION_PATH.read_text().strip()

# Set to "native" by deploy/install.sh in backend/.env; absent (empty) on
# Docker and manual setups.  Determines whether the "Update now" UI button
# and /api/system/update endpoint are available.
INSTALL_METHOD = os.environ.get("TILORA_INSTALL_METHOD", "")

# Repo root — one level above BACKEND_ROOT (which is backend/).  Used by
# run_update() to locate the git checkout and frontend directory.
INSTALL_DIR = BACKEND_ROOT.parent

# Populated by `check_for_update`; kept as the last-known-good result if a
# check fails, rather than resetting to "no update" on a transient error.
_latest: dict[str, Any] = {"latest_version": None, "release_url": None}

# Tracks the state of an in-progress in-place update (native installs only).
# `running` is True from the moment run_update() starts until it finishes
# (either by completing the restart or by erroring out).  `error` holds the
# last failure message so the UI can surface it.
_update_state: dict[str, Any] = {"running": False, "error": None}


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _is_newer(latest: str | None, current: str) -> bool:
    if latest is None:
        return False
    return _version_tuple(latest) > _version_tuple(current)


async def check_for_update() -> None:
    url = f"https://api.github.com/repos/{settings.github_repo}/releases/latest"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers={"Accept": "application/vnd.github+json"})
            response.raise_for_status()
            data = response.json()
        _latest["latest_version"] = data["tag_name"].lstrip("v")
        _latest["release_url"] = data["html_url"]
    except Exception:
        # Leave the previous result in place — a network blip or GitHub
        # rate limit shouldn't flip the UI back to "no update available".
        logger.exception("Failed to check for updates")


def get_update_status() -> dict[str, Any]:
    latest_version = _latest["latest_version"]
    return {
        "current_version": CURRENT_VERSION,
        "latest_version": latest_version,
        "update_available": _is_newer(latest_version, CURRENT_VERSION),
        "release_url": _latest["release_url"],
        "install_method": INSTALL_METHOD,
        "update_running": _update_state["running"],
    }


async def run_update() -> None:
    """Pull latest code, rebuild both services, and restart via sudoers wrapper.

    Runs as a FastAPI background task (see app.api.system).  The final step
    — `sudo deploy/restart.sh` — kills this process; systemd restarts the
    backend automatically, so the frontend's health-check poll eventually
    succeeds and the UI knows the update is done.

    Any subprocess failure sets _update_state["error"] and leaves the
    services running with whatever code they had before.
    """
    _update_state["running"] = True
    _update_state["error"] = None
    repository_ref = os.environ.get("TILORA_REPOSITORY_REF", "main")
    restart_script = str(INSTALL_DIR / "deploy" / "restart.sh")
    try:
        logger.info("Starting in-place update (ref=%s)", repository_ref)

        await asyncio.to_thread(
            subprocess.run,
            ["git", "-C", str(INSTALL_DIR), "fetch", "--quiet", "origin", repository_ref],
            check=True,
            capture_output=True,
        )
        await asyncio.to_thread(
            subprocess.run,
            ["git", "-C", str(INSTALL_DIR), "merge", "--ff-only", f"origin/{repository_ref}"],
            check=True,
            capture_output=True,
        )

        uv_bin = os.path.expanduser("~/.local/bin/uv")
        env = {**os.environ, "PATH": f"{os.path.dirname(uv_bin)}:{os.environ.get('PATH', '')}"}
        await asyncio.to_thread(
            subprocess.run,
            [uv_bin, "sync"],
            cwd=str(INSTALL_DIR / "backend"),
            check=True,
            capture_output=True,
            env=env,
        )

        await asyncio.to_thread(
            subprocess.run,
            ["npm", "ci"],
            cwd=str(INSTALL_DIR / "frontend"),
            check=True,
            capture_output=True,
        )
        await asyncio.to_thread(
            subprocess.run,
            ["npm", "run", "build"],
            cwd=str(INSTALL_DIR / "frontend"),
            check=True,
            capture_output=True,
        )

        logger.info("Build complete — restarting services via %s", restart_script)
        # This kills the process; systemd brings it back up.
        await asyncio.to_thread(
            subprocess.run,
            ["sudo", restart_script],
            check=True,
        )
    except Exception:
        logger.exception("In-place update failed")
        _update_state["error"] = "Update failed — check the service logs for details."
    finally:
        # Only reached if the restart itself failed (successful restart kills us).
        _update_state["running"] = False


def schedule_update_check(scheduler: Any) -> None:
    from apscheduler.triggers.cron import CronTrigger

    scheduler.add_job(
        check_for_update,
        trigger=CronTrigger.from_crontab("0 6 * * *"),
        id="update-check",
        replace_existing=True,
    )
