from __future__ import annotations

from unittest.mock import patch

from app.plugins.system_monitor.plugin import SystemMonitorPlugin

_DETAIL = {
    "hostname": "dashboard-host",
    "cpu_percent": 12.5,
    "cpu_count": 8,
    "cpu_per_core": [10.0, 15.0],
    "memory_percent": 42.0,
    "memory_used_gb": 6.7,
    "memory_total_gb": 16.0,
    "disk_percent": 55.0,
    "disk_used_gb": 100.0,
    "disk_total_gb": 200.0,
    "network_sent_gb": 1.2,
    "network_recv_gb": 3.4,
    "uptime_seconds": 3600,
    "load_average": [0.5, 0.7, 0.9],
}


def make_plugin() -> SystemMonitorPlugin:
    return SystemMonitorPlugin({"id": "system_monitor", "settings": {}})


async def test_get_detail_returns_collected_stats():
    plugin = make_plugin()

    with patch("app.plugins.system_monitor.plugin._collect_detail", return_value=_DETAIL):
        detail = await plugin.get_detail()

    assert detail == _DETAIL


async def test_get_summary_returns_headline_fields_only():
    plugin = make_plugin()

    with patch("app.plugins.system_monitor.plugin._collect_detail", return_value=_DETAIL):
        summary = await plugin.get_summary()

    assert summary == {
        "hostname": "dashboard-host",
        "cpu_percent": 12.5,
        "memory_percent": 42.0,
        "disk_percent": 55.0,
    }
