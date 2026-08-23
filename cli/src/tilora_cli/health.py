"""Backend health-check polling, shared by `restart` and `update`.

Same shape as deploy/update.sh's wait_for_health(): 30 attempts, 2s apart.
"""

from __future__ import annotations

import time

import click
import httpx

from tilora_cli.constants import HEALTH_CHECK_ATTEMPTS, HEALTH_CHECK_INTERVAL_SECONDS, HEALTH_URL


def is_healthy() -> bool:
    try:
        response = httpx.get(HEALTH_URL, timeout=5.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def wait_for_health() -> None:
    click.echo("Waiting for the backend health check...")
    for _ in range(HEALTH_CHECK_ATTEMPTS):
        if is_healthy():
            click.secho("Backend is healthy.", fg="green")
            return
        time.sleep(HEALTH_CHECK_INTERVAL_SECONDS)
    raise click.ClickException("The backend did not become healthy. Check the service logs: tilora logs --backend")
