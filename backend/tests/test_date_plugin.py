from __future__ import annotations

from app.plugins.date.plugin import DatePlugin


def make_plugin() -> DatePlugin:
    return DatePlugin({"id": "date", "settings": {}})


async def test_get_summary_reports_configured_timezone(tmp_db):
    from app.storage import db

    db.save_app_settings({"timezone": "America/Chicago"})
    plugin = make_plugin()

    assert await plugin.get_summary() == {"timezone": "America/Chicago"}


async def test_get_summary_falls_back_to_default_timezone(tmp_db):
    plugin = make_plugin()

    assert await plugin.get_summary() == {"timezone": "UTC"}


async def test_get_detail_matches_get_summary(tmp_db):
    plugin = make_plugin()

    assert await plugin.get_detail() == await plugin.get_summary()
