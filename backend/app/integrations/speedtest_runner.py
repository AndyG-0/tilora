"""Runs a network speedtest via the `speedtest-cli` library.

Unlike every other `app.integrations.*` module, this isn't a thin HTTP
client the caller awaits directly — `speedtest-cli`'s API is fully
synchronous and blocks on network I/O across its config fetch, server
selection, and download/upload phases (tens of seconds total), so
`run_speedtest()` is a plain blocking function. Callers run it off the
event loop via `asyncio.to_thread` — see `app.scheduler.run_speedtest_widget`.
"""

from __future__ import annotations

from typing import Any

import speedtest


class SpeedtestError(Exception):
    """Raised when a speedtest run can't be completed or its result parsed."""


def run_speedtest() -> dict[str, Any]:
    try:
        client = speedtest.Speedtest()
        client.get_best_server()
        client.download()
        client.upload()
        results = client.results.dict()
    except Exception as exc:
        raise SpeedtestError(f"Speedtest run failed: {exc}") from exc

    server = results.get("server") or {}
    server_name = server.get("sponsor") or server.get("name") or "Unknown server"
    try:
        return {
            "download_mbps": results["download"] / 1_000_000,
            "upload_mbps": results["upload"] / 1_000_000,
            "ping_ms": results["ping"],
            "server_name": server_name,
        }
    except (KeyError, TypeError) as exc:
        raise SpeedtestError(f"Speedtest returned an unexpected result shape: {exc}") from exc
