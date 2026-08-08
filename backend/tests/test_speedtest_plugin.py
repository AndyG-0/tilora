from __future__ import annotations

from app.plugins.speedtest.plugin import SpeedtestPlugin
from app.storage import db


def make_plugin(**settings) -> SpeedtestPlugin:
    return SpeedtestPlugin({"id": "speedtest", "settings": {"title": "Speedtest", "interval_minutes": 60, **settings}})


async def test_get_summary_with_no_prior_run(tmp_db):
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary == {
        "title": "Speedtest",
        "ran_at": None,
        "download_mbps": None,
        "upload_mbps": None,
        "ping_ms": None,
        "server_name": None,
    }


async def test_get_summary_returns_latest_run(tmp_db):
    plugin = make_plugin()
    db.record_speedtest_run(plugin.id, download_mbps=150.5, upload_mbps=20.1, ping_ms=12.3, server_name="Acme ISP")

    summary = await plugin.get_summary()

    assert summary["title"] == "Speedtest"
    assert summary["download_mbps"] == 150.5
    assert summary["upload_mbps"] == 20.1
    assert summary["ping_ms"] == 12.3
    assert summary["server_name"] == "Acme ISP"
    assert summary["ran_at"] is not None


async def test_get_detail_includes_history(tmp_db):
    plugin = make_plugin()
    db.record_speedtest_run(plugin.id, download_mbps=100.0, upload_mbps=10.0, ping_ms=15.0, server_name="First")
    db.record_speedtest_run(plugin.id, download_mbps=200.0, upload_mbps=20.0, ping_ms=10.0, server_name="Second")

    detail = await plugin.get_detail()

    assert detail["server_name"] == "Second"
    assert len(detail["history"]) == 2
    assert [run["server_name"] for run in detail["history"]] == ["Second", "First"]


async def test_get_detail_includes_interval_minutes(tmp_db):
    plugin = make_plugin(interval_minutes=30)

    detail = await plugin.get_detail()

    assert detail["interval_minutes"] == 30


async def test_interval_minutes_defaults_to_sixty(tmp_db):
    plugin = SpeedtestPlugin({"id": "speedtest", "settings": {}})

    assert plugin.interval_minutes == 60
