from __future__ import annotations

from typing import Any

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.scheduler as scheduler_module
from app.api import widgets
from app.auth import get_current_device, get_current_user
from app.plugins.ai_insights.plugin import AIInsightsPlugin
from app.plugins.base import Plugin, registry
from app.plugins.photos.plugin import PhotosPlugin
from app.storage import db

TEST_USER_ID = "test-user"
TEST_DEVICE_ID = "test-device"


class StubPlugin(Plugin):
    id = "stub"
    name = "Stub"
    refresh_interval_seconds = 300

    def __init__(self, config):
        super().__init__(config)
        self.summary_calls = 0
        self.detail_calls = 0

    async def get_summary(self) -> dict[str, Any]:
        self.summary_calls += 1
        return {"value": "summary"}

    async def get_detail(self) -> dict[str, Any]:
        self.detail_calls += 1
        return {"value": "detail"}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(widgets.router)
    # These tests exercise widget-list/layout logic, not auth — stub out
    # who's asking rather than juggling real device/session cookies here
    # (that's what test_api_auth_flow.py covers end to end).
    app.dependency_overrides[get_current_user] = lambda: {"id": TEST_USER_ID}
    app.dependency_overrides[get_current_device] = lambda: {"id": TEST_DEVICE_ID}
    return TestClient(app)


@pytest.fixture
def dashboard_yaml(tmp_path, monkeypatch):
    path = tmp_path / "dashboard.yaml"
    path.write_text(
        """
widgets:
  - id: stub
    type: stub
    enabled: true
    layout: { col: 1, row: 1, colSpan: 1, rowSpan: 1 }
    settings: {}
  - id: hidden
    type: stub
    enabled: false
    layout: { col: 2, row: 1, colSpan: 1, rowSpan: 1 }
    settings: {}
"""
    )
    monkeypatch.setattr("app.api.widgets.load_dashboard_config", lambda: yaml.safe_load(path.read_text()))
    return path


def test_list_widgets_excludes_disabled(client, dashboard_yaml, tmp_db):
    response = client.get("/api/widgets")
    assert response.status_code == 200
    assert response.json() == [
        {"id": "stub", "type": "stub", "layout": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}, "tab": "default"}
    ]


def test_list_widgets_includes_explicit_tab(client, tmp_path, monkeypatch, tmp_db):
    path = tmp_path / "dashboard.yaml"
    path.write_text(
        """
tabs:
  - id: home
    name: Home
  - id: media
    name: Media
widgets:
  - id: stub
    type: stub
    enabled: true
    layout: { col: 1, row: 1, colSpan: 1, rowSpan: 1 }
    tab: media
    settings: {}
  - id: no-tab
    type: stub
    enabled: true
    layout: { col: 2, row: 1, colSpan: 1, rowSpan: 1 }
    settings: {}
"""
    )
    monkeypatch.setattr("app.api.widgets.load_dashboard_config", lambda: yaml.safe_load(path.read_text()))

    response = client.get("/api/widgets")

    assert response.status_code == 200
    tabs_by_id = {w["id"]: w["tab"] for w in response.json()}
    assert tabs_by_id == {"stub": "media", "no-tab": "home"}


def test_list_widgets_reflects_persisted_layout_override(client, dashboard_yaml, tmp_db):
    db.save_widget_layout(TEST_USER_ID, TEST_DEVICE_ID, "stub", {"col": 3, "row": 2, "colSpan": 1, "rowSpan": 1})

    response = client.get("/api/widgets")

    assert response.status_code == 200
    assert response.json()[0]["layout"] == {"col": 3, "row": 2, "colSpan": 1, "rowSpan": 1}


def test_update_widgets_layout_persists_and_swaps(client, dashboard_yaml, tmp_db):
    response = client.put(
        "/api/widgets/layout",
        json={
            "widgets": [
                {"id": "stub", "layout": {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1}},
                {"id": "hidden", "layout": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}},
            ]
        },
    )

    assert response.status_code == 200
    assert db.get_widget_layout(TEST_USER_ID, TEST_DEVICE_ID, "stub") == {
        "col": 2,
        "row": 1,
        "colSpan": 1,
        "rowSpan": 1,
    }
    assert db.get_widget_layout(TEST_USER_ID, TEST_DEVICE_ID, "hidden") == {
        "col": 1,
        "row": 1,
        "colSpan": 1,
        "rowSpan": 1,
    }


def test_summary_returns_404_for_unregistered_widget(client, dashboard_yaml):
    response = client.get("/api/widgets/nonexistent/summary")
    assert response.status_code == 404


def test_summary_returns_plugin_data(client, dashboard_yaml):
    plugin = StubPlugin({})
    registry.register(plugin)

    response = client.get("/api/widgets/stub/summary")

    assert response.status_code == 200
    assert response.json() == {"value": "summary"}


def test_summary_is_cached_between_requests(client, dashboard_yaml):
    plugin = StubPlugin({})
    registry.register(plugin)

    client.get("/api/widgets/stub/summary")
    client.get("/api/widgets/stub/summary")

    assert plugin.summary_calls == 1


def test_detail_returns_plugin_data(client, dashboard_yaml):
    plugin = StubPlugin({})
    registry.register(plugin)

    response = client.get("/api/widgets/stub/detail")

    assert response.status_code == 200
    assert response.json() == {"value": "detail"}


def test_update_settings_returns_404_for_unregistered_widget(client, dashboard_yaml):
    response = client.patch("/api/widgets/nonexistent/settings", json={"a": 1})
    assert response.status_code == 404


def test_update_settings_merges_into_plugin_config(client, dashboard_yaml, tmp_db):
    plugin = StubPlugin({"settings": {"a": 1, "b": 2}})
    registry.register(plugin)

    response = client.patch("/api/widgets/stub/settings", json={"b": 3, "c": 4})

    assert response.status_code == 200
    assert response.json() == {"a": 1, "b": 3, "c": 4}
    assert plugin.config["settings"] == {"a": 1, "b": 3, "c": 4}


def test_update_settings_persists_to_db(client, dashboard_yaml, tmp_db):
    plugin = StubPlugin({"settings": {"a": 1}})
    registry.register(plugin)

    client.patch("/api/widgets/stub/settings", json={"a": 2})

    assert db.get_widget_settings("stub") == {"a": 2}


def test_update_settings_invalidates_cached_summary_and_detail(client, dashboard_yaml, tmp_db):
    plugin = StubPlugin({"settings": {}})
    registry.register(plugin)
    client.get("/api/widgets/stub/summary")
    client.get("/api/widgets/stub/detail")
    assert plugin.summary_calls == 1
    assert plugin.detail_calls == 1

    client.patch("/api/widgets/stub/settings", json={"a": 1})
    client.get("/api/widgets/stub/summary")
    client.get("/api/widgets/stub/detail")

    assert plugin.summary_calls == 2
    assert plugin.detail_calls == 2


def test_update_settings_reindexes_when_a_source_relevant_key_changes(client, dashboard_yaml, tmp_db, monkeypatch):
    plugin = PhotosPlugin({"id": "photos", "settings": {"provider": "local", "directory": "/a"}})
    registry.register(plugin)
    calls = []
    monkeypatch.setattr(widgets, "schedule_photo_index", lambda p: calls.append(p.id))

    client.patch("/api/widgets/photos/settings", json={"directory": "/b"})

    assert calls == ["photos"]


def test_update_settings_skips_reindex_for_unrelated_keys(client, dashboard_yaml, tmp_db, monkeypatch):
    plugin = PhotosPlugin({"id": "photos", "settings": {"provider": "local", "directory": "/a"}})
    registry.register(plugin)
    calls = []
    monkeypatch.setattr(widgets, "schedule_photo_index", lambda p: calls.append(p.id))

    client.patch("/api/widgets/photos/settings", json={"interval_seconds": 15})

    assert calls == []


def test_run_returns_404_for_unregistered_widget(client, dashboard_yaml):
    response = client.post("/api/widgets/nonexistent/run")
    assert response.status_code == 404


def test_run_returns_400_for_non_ai_widget(client, dashboard_yaml):
    plugin = StubPlugin({})
    registry.register(plugin)

    response = client.post("/api/widgets/stub/run")

    assert response.status_code == 400


def test_run_triggers_generation_and_returns_fresh_detail(client, dashboard_yaml, tmp_db, monkeypatch):
    plugin = AIInsightsPlugin({"settings": {"title": "Briefing", "cron": "30 6 * * *", "prompt": "Say hello"}})
    registry.register(plugin)

    async def fake_run_ai_widget(run_plugin):
        assert run_plugin is plugin
        db.record_ai_run(run_plugin.id, {"text": "Fresh briefing"})

    monkeypatch.setattr(widgets, "run_ai_widget", fake_run_ai_widget)

    response = client.post("/api/widgets/ai-insights/run")

    assert response.status_code == 200
    assert response.json()["text"] == "Fresh briefing"


def test_widget_types_lists_all_registered_types(client):
    response = client.get("/api/widgets/types")

    assert response.status_code == 200
    types = {entry["type"] for entry in response.json()}
    assert "weather" in types
    assert "ai" in types


def test_add_widget_registers_plugin_and_persists(client, dashboard_yaml, tmp_db):
    response = client.post(
        "/api/widgets",
        json={"type": "clock", "layout": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}, "tab": "home"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "clock"
    assert body["tab"] == "home"
    assert body["id"].startswith("clock-")
    assert registry.get(body["id"]) is not None
    assert db.list_custom_widgets()[0]["id"] == body["id"]


def test_add_widget_appears_in_list_widgets(client, dashboard_yaml, tmp_db):
    add_response = client.post(
        "/api/widgets",
        json={"type": "clock", "layout": {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1}, "tab": "default"},
    )
    widget_id = add_response.json()["id"]

    response = client.get("/api/widgets")

    ids = [w["id"] for w in response.json()]
    assert widget_id in ids


def test_add_widget_persists_default_settings(client, dashboard_yaml, tmp_db):
    try:
        response = client.post(
            "/api/widgets",
            json={"type": "ai", "layout": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}},
        )
        widget_id = response.json()["id"]

        assert db.get_widget_settings(widget_id) == AIInsightsPlugin.default_settings
    finally:
        scheduler_module.scheduler.remove_all_jobs()


def test_add_widget_schedules_ai_widget_cron_job(client, dashboard_yaml, tmp_db):
    try:
        response = client.post(
            "/api/widgets",
            json={"type": "ai", "layout": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}},
        )
        widget_id = response.json()["id"]

        assert scheduler_module.scheduler.get_job(f"ai-widget:{widget_id}") is not None
    finally:
        scheduler_module.scheduler.remove_all_jobs()


def test_add_widget_schedules_photo_index_job(client, dashboard_yaml, tmp_db):
    try:
        response = client.post(
            "/api/widgets",
            json={"type": "photos", "layout": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}},
        )
        widget_id = response.json()["id"]

        assert scheduler_module.scheduler.get_job(f"photo-index:{widget_id}") is not None
    finally:
        scheduler_module.scheduler.remove_all_jobs()


def test_add_widget_returns_400_for_unknown_type(client, dashboard_yaml, tmp_db):
    response = client.post(
        "/api/widgets",
        json={"type": "nonexistent", "layout": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}},
    )

    assert response.status_code == 400


def test_remove_widget_returns_404_for_unregistered_widget(client, dashboard_yaml, tmp_db):
    response = client.delete("/api/widgets/nonexistent")
    assert response.status_code == 404


def test_remove_widget_unregisters_yaml_widget_via_soft_delete(client, dashboard_yaml, tmp_db):
    plugin = StubPlugin({})
    registry.register(plugin)

    response = client.delete("/api/widgets/stub")

    assert response.status_code == 200
    assert registry.get("stub") is None
    assert "stub" in db.removed_widget_ids()


def test_remove_widget_hides_yaml_widget_from_list(client, dashboard_yaml, tmp_db):
    registry.register(StubPlugin({}))

    client.delete("/api/widgets/stub")

    response = client.get("/api/widgets")
    assert "stub" not in [w["id"] for w in response.json()]


def test_remove_widget_deletes_custom_widget_entirely(client, dashboard_yaml, tmp_db):
    add_response = client.post(
        "/api/widgets",
        json={"type": "clock", "layout": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}},
    )
    widget_id = add_response.json()["id"]

    response = client.delete(f"/api/widgets/{widget_id}")

    assert response.status_code == 200
    assert registry.get(widget_id) is None
    assert db.list_custom_widgets() == []
    assert widget_id not in db.removed_widget_ids()


def test_remove_widget_deletes_photo_index_rows(client, dashboard_yaml, tmp_db):
    plugin = PhotosPlugin({"id": "photos", "settings": {"provider": "local", "directory": "/a"}})
    registry.register(plugin)
    generation = db.begin_photo_index_scan(plugin.id)
    db.upsert_photo_index_chunk(plugin.id, generation, ["a.jpg"], 0)
    db.finish_photo_index_scan(plugin.id, generation)
    assert db.photo_index_photo_ids(plugin.id) == ["a.jpg"]

    response = client.delete("/api/widgets/photos")

    assert response.status_code == 200
    assert db.photo_index_photo_ids(plugin.id) == []
    assert db.photo_index_status(plugin.id) is None


def test_run_invalidates_cached_summary_and_detail(client, dashboard_yaml, tmp_db, monkeypatch):
    plugin = AIInsightsPlugin({"settings": {"title": "Briefing", "cron": "30 6 * * *", "prompt": "Say hello"}})
    registry.register(plugin)
    db.record_ai_run(plugin.id, {"text": "Stale briefing"})
    client.get("/api/widgets/ai-insights/summary")
    client.get("/api/widgets/ai-insights/detail")

    async def fake_run_ai_widget(run_plugin):
        db.record_ai_run(run_plugin.id, {"text": "Fresh briefing"})

    monkeypatch.setattr(widgets, "run_ai_widget", fake_run_ai_widget)
    client.post("/api/widgets/ai-insights/run")

    assert client.get("/api/widgets/ai-insights/summary").json()["text"] == "Fresh briefing"
    assert client.get("/api/widgets/ai-insights/detail").json()["text"] == "Fresh briefing"
