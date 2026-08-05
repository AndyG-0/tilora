from __future__ import annotations

import re

from app.plugins.clock.plugin import ClockPlugin


def make_plugin() -> ClockPlugin:
    return ClockPlugin({"id": "clock", "settings": {}})


async def test_get_summary_reports_configured_timezone(tmp_db):
    from app.storage import db

    db.save_app_settings({"timezone": "America/Chicago"})
    plugin = make_plugin()

    assert await plugin.get_summary() == {"timezone": "America/Chicago", "style": "digital"}


async def test_get_summary_falls_back_to_default_timezone(tmp_db):
    plugin = make_plugin()

    assert await plugin.get_summary() == {"timezone": "UTC", "style": "digital"}


async def test_get_summary_reports_configured_style(tmp_db):
    plugin = ClockPlugin({"id": "clock", "settings": {"style": "analog"}})

    assert await plugin.get_summary() == {"timezone": "UTC", "style": "analog"}


async def test_get_detail_matches_get_summary(tmp_db):
    plugin = make_plugin()

    assert await plugin.get_detail() == await plugin.get_summary()


async def test_get_ai_tools_exposes_current_time_tool(tmp_db):
    from app.storage import db

    db.save_app_settings({"timezone": "America/Chicago"})
    plugin = make_plugin()

    tools = plugin.get_ai_tools()

    assert [t.name for t in tools] == ["get_current_time_clock"]
    result = await tools[0].handler()

    assert result["timezone"] == "America/Chicago"
    assert re.fullmatch(r"\d{1,2}:\d{2} (AM|PM)", result["time"])


async def test_get_ai_tools_current_time_falls_back_to_utc_for_unknown_timezone(tmp_db):
    from app.storage import db

    db.save_app_settings({"timezone": "Not/A_Real_Zone"})
    plugin = make_plugin()

    tools = plugin.get_ai_tools()
    result = await tools[0].handler()

    assert result["timezone"] == "Not/A_Real_Zone"
    assert re.fullmatch(r"\d{1,2}:\d{2} (AM|PM)", result["time"])
