"""System resource monitor plugin: CPU/RAM/disk/network usage for the host
running the backend, via `psutil`. Runs entirely locally — no external
service, auth, or network client needed, so unlike pihole/hdhomerun there's
no "not configured" state to handle.
"""

from __future__ import annotations

import asyncio
import socket
import time
from typing import Any, ClassVar

import psutil

from app.plugins.base import Plugin

_ROOT_PATH = "/"
_CPU_SAMPLE_INTERVAL_SECONDS = 0.3


def _bytes_to_gb(value: int) -> float:
    return round(value / (1024**3), 1)


def _collect_detail() -> dict[str, Any]:
    # A single blocking sample interval covers both the overall and
    # per-core figures, rather than sampling twice with inconsistent timing.
    cpu_per_core = psutil.cpu_percent(interval=_CPU_SAMPLE_INTERVAL_SECONDS, percpu=True)
    cpu_percent = round(sum(cpu_per_core) / len(cpu_per_core), 1) if cpu_per_core else 0.0
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(_ROOT_PATH)
    net = psutil.net_io_counters()
    load_1m, load_5m, load_15m = psutil.getloadavg()

    return {
        "hostname": socket.gethostname(),
        "cpu_percent": cpu_percent,
        "cpu_count": psutil.cpu_count(logical=True) or len(cpu_per_core),
        "cpu_per_core": cpu_per_core,
        "memory_percent": memory.percent,
        "memory_used_gb": _bytes_to_gb(memory.used),
        "memory_total_gb": _bytes_to_gb(memory.total),
        "disk_percent": disk.percent,
        "disk_used_gb": _bytes_to_gb(disk.used),
        "disk_total_gb": _bytes_to_gb(disk.total),
        "network_sent_gb": _bytes_to_gb(net.bytes_sent),
        "network_recv_gb": _bytes_to_gb(net.bytes_recv),
        "uptime_seconds": int(time.time() - psutil.boot_time()),
        "load_average": [load_1m, load_5m, load_15m],
    }


class SystemMonitorPlugin(Plugin):
    id = "system_monitor"
    name = "System Monitor"
    refresh_interval_seconds = 10
    default_layout: ClassVar[dict[str, int]] = {"colSpan": 2, "rowSpan": 1}

    async def get_detail(self) -> dict[str, Any]:
        # psutil's calls are blocking (the CPU sample alone sleeps for
        # _CPU_SAMPLE_INTERVAL_SECONDS), so run them off the event loop.
        return await asyncio.to_thread(_collect_detail)

    async def get_summary(self) -> dict[str, Any]:
        detail = await self.get_detail()
        return {
            "hostname": detail["hostname"],
            "cpu_percent": detail["cpu_percent"],
            "memory_percent": detail["memory_percent"],
            "disk_percent": detail["disk_percent"],
        }
