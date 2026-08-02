"""Checks GitHub releases for newer versions of the project.

Surfaces a simple "an update is available" signal to the UI
(`app.api.version`) — no auto-update, just notification. See `VERSION` at
the repo root for the current version and the project README for the
release-tagging convention (`vX.Y.Z`).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import BACKEND_ROOT, settings

logger = logging.getLogger(__name__)

VERSION_PATH = BACKEND_ROOT.parent / "VERSION"

CURRENT_VERSION = VERSION_PATH.read_text().strip()

# Populated by `check_for_update`; kept as the last-known-good result if a
# check fails, rather than resetting to "no update" on a transient error.
_latest: dict[str, Any] = {"latest_version": None, "release_url": None}


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
    }


def schedule_update_check(scheduler: Any) -> None:
    from apscheduler.triggers.cron import CronTrigger

    scheduler.add_job(
        check_for_update,
        trigger=CronTrigger.from_crontab("0 6 * * *"),
        id="update-check",
        replace_existing=True,
    )
