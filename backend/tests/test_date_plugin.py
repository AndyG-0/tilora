from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

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


async def test_get_ai_tools_exposes_current_date_tool(tmp_db):
    from app.storage import db

    db.save_app_settings({"timezone": "America/Chicago"})
    plugin = make_plugin()

    tools = plugin.get_ai_tools()

    assert [t.name for t in tools] == ["get_current_date_date"]
    result = await tools[0].handler()

    now = datetime.now(ZoneInfo("America/Chicago"))
    assert result == {
        "date": f"{now:%A, %B} {now.day}, {now.year}",
        "timezone": "America/Chicago",
    }


async def test_get_ai_tools_current_date_falls_back_to_utc_for_unknown_timezone(tmp_db):
    from app.storage import db

    db.save_app_settings({"timezone": "Not/A_Real_Zone"})
    plugin = make_plugin()

    tools = plugin.get_ai_tools()
    result = await tools[0].handler()

    now = datetime.now(ZoneInfo("UTC"))
    assert result == {
        "date": f"{now:%A, %B} {now.day}, {now.year}",
        "timezone": "Not/A_Real_Zone",
    }
