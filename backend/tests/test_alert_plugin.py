from __future__ import annotations

from app.plugins.alert.plugin import AlertPlugin


def make_plugin() -> AlertPlugin:
    return AlertPlugin({"id": "alert", "settings": {}})


async def test_get_summary_with_no_alerts(tmp_db):
    plugin = make_plugin()

    assert await plugin.get_summary() == {"count": 0, "most_urgent": None}


async def test_get_summary_orders_by_severity_not_recency(tmp_db):
    plugin = make_plugin()
    from app.storage import db

    db.create_alert("alert", "Just info", "info")
    db.create_alert("alert", "Urgent!", "critical")

    summary = await plugin.get_summary()

    assert summary["count"] == 2
    assert summary["most_urgent"]["message"] == "Urgent!"


async def test_get_detail_lists_all_active_alerts(tmp_db):
    plugin = make_plugin()
    from app.storage import db

    db.create_alert("alert", "First", "info")
    db.create_alert("alert", "Second", "warning")

    detail = await plugin.get_detail()

    messages = {a["message"] for a in detail["alerts"]}
    assert messages == {"First", "Second"}


async def test_create_alert_tool_persists_alert(tmp_db):
    plugin = make_plugin()
    tools = {t.name: t for t in plugin.get_ai_tools()}

    result = await tools["create_alert"].handler(message="Tool made me", severity="warning")

    assert result["message"] == "Tool made me"
    assert result["severity"] == "warning"
    detail = await plugin.get_detail()
    assert detail["alerts"][0]["message"] == "Tool made me"


async def test_create_alert_tool_defaults_severity_to_info(tmp_db):
    plugin = make_plugin()
    tools = {t.name: t for t in plugin.get_ai_tools()}

    result = await tools["create_alert"].handler(message="Default severity")

    assert result["severity"] == "info"
