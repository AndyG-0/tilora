from __future__ import annotations

import logging
from typing import Any

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.scheduler as scheduler_module
from app.api import widgets
from app.auth import get_current_device, get_current_user
from app.plugins import scoping
from app.plugins.ai_insights.plugin import AIInsightsPlugin
from app.plugins.base import Plugin, registry
from app.plugins.container.plugin import ContainerPlugin
from app.plugins.hdhomerun.plugin import HDHomeRunPlugin
from app.plugins.photos.plugin import PhotosPlugin
from app.plugins.pihole.plugin import PiholePlugin
from app.plugins.speedtest.plugin import SpeedtestPlugin
from app.plugins.sports.plugin import SportsPlugin
from app.plugins.weather.plugin import WeatherPlugin
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


class StubPersonalPlugin(StubPlugin):
    """A personal-scope stub whose content reflects its own settings, so a
    test can tell whether it's serving one user's settings vs. another's."""

    id = "personal-stub"
    name = "Stub Personal"
    settings_scope = "personal"

    async def get_summary(self) -> dict[str, Any]:
        self.summary_calls += 1
        return {"value": self.config["settings"].get("value", "default")}

    async def get_detail(self) -> dict[str, Any]:
        self.detail_calls += 1
        return {"value": self.config["settings"].get("value", "default")}


class StubDeviceOverridablePlugin(StubPlugin):
    """A network-scope stub with one device-overridable key, so a test can
    tell a household default apart from a per-device override."""

    id = "device-stub"
    name = "Stub Device Overridable"
    device_overridable_settings = frozenset({"value"})

    async def get_summary(self) -> dict[str, Any]:
        self.summary_calls += 1
        return {"value": self.config["settings"].get("value", "default")}

    async def get_detail(self) -> dict[str, Any]:
        self.detail_calls += 1
        return {"value": self.config["settings"].get("value", "default")}


class StubLocaleAwarePlugin(StubPlugin):
    """A stub whose content reflects `self.locale`, so a test can tell which
    locale a given response was rendered for."""

    id = "locale-stub"
    name = "Stub Locale Aware"

    async def get_summary(self) -> dict[str, Any]:
        self.summary_calls += 1
        return {"value": self.locale}

    async def get_detail(self) -> dict[str, Any]:
        self.detail_calls += 1
        return {"value": self.locale}


class StubValidatingPlugin(StubPlugin):
    """A stub that rejects a settings patch, covering the Plugin.validate_settings
    hook — the point of which is that a bad value never reaches the database."""

    id = "validating-stub"
    name = "Stub Validating"

    def validate_settings(self, payload: dict[str, Any]) -> None:
        if payload.get("value") == "bad":
            raise ValueError("value 'bad' is not allowed")


class StubPersonalDeviceOverridablePlugin(StubPlugin):
    """A personal-scope stub with one device-overridable key. No shipped
    plugin combines these two today, but Plugin.device_overridable_settings
    documents the combination as supported, so this covers the cache
    invalidation path for it."""

    id = "personal-device-stub"
    name = "Stub Personal Device Overridable"
    settings_scope = "personal"
    device_overridable_settings = frozenset({"value"})

    async def get_summary(self) -> dict[str, Any]:
        self.summary_calls += 1
        return {"value": self.config["settings"].get("value", "default")}

    async def get_detail(self) -> dict[str, Any]:
        self.detail_calls += 1
        return {"value": self.config["settings"].get("value", "default")}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(widgets.router)
    # These tests exercise widget-list/layout/settings logic, not auth — stub
    # out who's asking (as an admin, so network-scope settings writes aren't
    # blocked by default) rather than juggling real device/session cookies
    # here (that's what test_api_auth_flow.py covers end to end). Scope/role
    # gating itself is covered by the dedicated tests further down, which
    # override this dependency per-test.
    app.dependency_overrides[get_current_user] = lambda: {"id": TEST_USER_ID, "role": "admin"}
    app.dependency_overrides[get_current_device] = lambda: {"id": TEST_DEVICE_ID}
    return TestClient(app)


@pytest.fixture
def member_client():
    """A non-admin household member, to exercise write-access gating."""
    app = FastAPI()
    app.include_router(widgets.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "member-user", "role": "member"}
    app.dependency_overrides[get_current_device] = lambda: {"id": TEST_DEVICE_ID}
    return TestClient(app)


@pytest.fixture
def unauthenticated_client():
    """No get_current_user override — exercises the real dependency, which
    401s when there's no session cookie."""
    app = FastAPI()
    app.include_router(widgets.router)
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
    response = client.get("/api/widgets?breakpoint=wide")
    assert response.status_code == 200
    assert response.json() == [
        {"id": "stub", "type": "stub", "layout": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}, "tab": "default"}
    ]


def test_list_widgets_requires_breakpoint_query_param(client, dashboard_yaml, tmp_db):
    response = client.get("/api/widgets")
    assert response.status_code == 422


def test_list_widgets_rejects_an_unknown_breakpoint(client, dashboard_yaml, tmp_db):
    response = client.get("/api/widgets?breakpoint=huge")
    assert response.status_code == 422


def test_list_widgets_narrow_and_wide_layouts_are_independent(client, dashboard_yaml, tmp_db):
    db.save_widget_layout(
        TEST_USER_ID, TEST_DEVICE_ID, "wide", "stub", {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}
    )
    db.save_widget_layout(
        TEST_USER_ID, TEST_DEVICE_ID, "narrow", "stub", {"col": 3, "row": 3, "colSpan": 2, "rowSpan": 2}
    )

    wide = client.get("/api/widgets?breakpoint=wide").json()
    narrow = client.get("/api/widgets?breakpoint=narrow").json()

    assert wide[0]["layout"] == {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}
    assert narrow[0]["layout"] == {"col": 3, "row": 3, "colSpan": 2, "rowSpan": 2}


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

    response = client.get("/api/widgets?breakpoint=wide")

    assert response.status_code == 200
    tabs_by_id = {w["id"]: w["tab"] for w in response.json()}
    assert tabs_by_id == {"stub": "media", "no-tab": "home"}


def test_list_widgets_reflects_persisted_layout_override(client, dashboard_yaml, tmp_db):
    db.save_widget_layout(
        TEST_USER_ID, TEST_DEVICE_ID, "wide", "stub", {"col": 3, "row": 2, "colSpan": 1, "rowSpan": 1}
    )

    response = client.get("/api/widgets?breakpoint=wide")

    assert response.status_code == 200
    assert response.json()[0]["layout"] == {"col": 3, "row": 2, "colSpan": 1, "rowSpan": 1}


def test_update_widgets_layout_persists_and_swaps(client, dashboard_yaml, tmp_db):
    response = client.put(
        "/api/widgets/layout",
        json={
            "breakpoint": "wide",
            "widgets": [
                {"id": "stub", "layout": {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1}},
                {"id": "hidden", "layout": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}},
            ],
        },
    )

    assert response.status_code == 200
    assert db.get_widget_layout(TEST_USER_ID, TEST_DEVICE_ID, "wide", "stub") == {
        "col": 2,
        "row": 1,
        "colSpan": 1,
        "rowSpan": 1,
    }
    assert db.get_widget_layout(TEST_USER_ID, TEST_DEVICE_ID, "wide", "hidden") == {
        "col": 1,
        "row": 1,
        "colSpan": 1,
        "rowSpan": 1,
    }


def test_summary_returns_404_for_unregistered_widget(client, dashboard_yaml):
    response = client.get("/api/widgets/nonexistent/summary")
    assert response.status_code == 404


def test_summary_returns_plugin_data(client, dashboard_yaml, tmp_db):
    plugin = StubPlugin({})
    registry.register(plugin)

    response = client.get("/api/widgets/stub/summary")

    assert response.status_code == 200
    assert response.json() == {"value": "summary"}


def test_summary_is_cached_between_requests(client, dashboard_yaml, tmp_db):
    plugin = StubPlugin({})
    registry.register(plugin)

    client.get("/api/widgets/stub/summary")
    client.get("/api/widgets/stub/summary")

    assert plugin.summary_calls == 1


def test_summary_logs_latency_tagged_with_widget_id(client, dashboard_yaml, tmp_db, caplog):
    plugin = StubPlugin({})
    registry.register(plugin)

    with caplog.at_level(logging.INFO, logger="app.api.widgets"):
        response = client.get("/api/widgets/stub/summary")

    assert response.status_code == 200
    assert any("stub" in r.message and "summary" in r.message for r in caplog.records)


def test_summary_logs_and_reraises_plugin_errors(client, dashboard_yaml, tmp_db, caplog):
    class FailingPlugin(StubPlugin):
        id = "failing-stub"

        async def get_summary(self) -> dict[str, Any]:
            raise RuntimeError("boom")

    plugin = FailingPlugin({})
    registry.register(plugin)

    with caplog.at_level(logging.ERROR, logger="app.api.widgets"):
        with pytest.raises(RuntimeError, match="boom"):
            client.get("/api/widgets/failing-stub/summary")

    assert any("failing-stub" in r.message and "failed" in r.message for r in caplog.records)


def test_detail_returns_plugin_data(client, dashboard_yaml, tmp_db):
    plugin = StubPlugin({})
    registry.register(plugin)

    response = client.get("/api/widgets/stub/detail")

    assert response.status_code == 200
    assert response.json() == {"value": "detail"}


def test_summary_reflects_users_locale_preference(client, dashboard_yaml, tmp_db):
    plugin = StubLocaleAwarePlugin({"settings": {}})
    registry.register(plugin)
    db.save_user_preferences(TEST_USER_ID, {"locale": "es"})

    response = client.get("/api/widgets/locale-stub/summary")

    assert response.json() == {"value": "es"}
    # Never mutated in place — scoped_plugin cloned a throwaway instance.
    assert plugin.locale == "en"


def test_summary_cache_is_scoped_per_locale(client, dashboard_yaml, tmp_db, monkeypatch):
    plugin = StubLocaleAwarePlugin({"settings": {}})
    registry.register(plugin)
    calls: list[str] = []
    original_get_summary = StubLocaleAwarePlugin.get_summary

    async def counting_get_summary(self):
        calls.append(self.locale)
        return await original_get_summary(self)

    monkeypatch.setattr(StubLocaleAwarePlugin, "get_summary", counting_get_summary)

    assert client.get("/api/widgets/locale-stub/summary").json() == {"value": "en"}
    db.save_user_preferences(TEST_USER_ID, {"locale": "es"})
    assert client.get("/api/widgets/locale-stub/summary").json() == {"value": "es"}

    # Distinct cache entries per locale — the Spanish request didn't serve
    # the already-cached English response, and both were computed once.
    assert calls == ["en", "es"]


def test_switching_locale_back_still_hits_the_original_cache_entry(client, dashboard_yaml, tmp_db, monkeypatch):
    plugin = StubLocaleAwarePlugin({"settings": {}})
    registry.register(plugin)
    calls: list[str] = []
    original_get_summary = StubLocaleAwarePlugin.get_summary

    async def counting_get_summary(self):
        calls.append(self.locale)
        return await original_get_summary(self)

    monkeypatch.setattr(StubLocaleAwarePlugin, "get_summary", counting_get_summary)

    client.get("/api/widgets/locale-stub/summary")
    db.save_user_preferences(TEST_USER_ID, {"locale": "es"})
    client.get("/api/widgets/locale-stub/summary")
    db.save_user_preferences(TEST_USER_ID, {"locale": "en"})
    response = client.get("/api/widgets/locale-stub/summary")

    assert response.json() == {"value": "en"}
    # The English response was already cached from the first request, so
    # switching back to it doesn't recompute — only the one-time Spanish
    # miss added a second call.
    assert calls == ["en", "es"]


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


def test_update_settings_returns_400_when_the_plugin_rejects_the_payload(client, dashboard_yaml, tmp_db):
    plugin = StubValidatingPlugin({"settings": {"value": "good"}})
    registry.register(plugin)

    response = client.patch("/api/widgets/validating-stub/settings", json={"value": "bad"})

    assert response.status_code == 400
    assert response.json()["detail"] == "value 'bad' is not allowed"
    # Rejected before anything is written, so neither the live plugin nor the
    # database is left holding the bad value.
    assert plugin.config["settings"] == {"value": "good"}
    assert db.get_widget_settings("validating-stub") is None


def test_update_settings_accepts_a_payload_the_plugin_allows(client, dashboard_yaml, tmp_db):
    plugin = StubValidatingPlugin({"settings": {"value": "good"}})
    registry.register(plugin)

    response = client.patch("/api/widgets/validating-stub/settings", json={"value": "also-good"})

    assert response.status_code == 200
    assert plugin.config["settings"] == {"value": "also-good"}


def test_update_settings_rejects_an_unknown_hdhomerun_hwaccel_preset(client, dashboard_yaml, tmp_db):
    # Regression test: an unrecognised preset used to degrade silently to
    # software in transcoding.resolve_preset, so the widget reported the
    # setting the user chose while running something else entirely.
    plugin = HDHomeRunPlugin({"id": "hdhomerun", "settings": {"hwaccel": "vaapi"}})
    registry.register(plugin)

    response = client.patch("/api/widgets/hdhomerun/settings", json={"hwaccel": "vappi"})

    assert response.status_code == 400
    assert "vappi" in response.json()["detail"]
    assert "vaapi" in response.json()["detail"]
    assert plugin.config["settings"]["hwaccel"] == "vaapi"


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


def test_update_settings_reschedules_speedtest_when_interval_changes(client, dashboard_yaml, tmp_db, monkeypatch):
    plugin = SpeedtestPlugin({"id": "speedtest", "settings": dict(SpeedtestPlugin.default_settings)})
    registry.register(plugin)
    calls = []
    monkeypatch.setattr(widgets, "schedule_speedtest_widget", lambda p: calls.append(p.id))

    client.patch("/api/widgets/speedtest/settings", json={"interval_minutes": 30})

    assert calls == ["speedtest"]


def test_update_settings_skips_speedtest_reschedule_for_unrelated_keys(client, dashboard_yaml, tmp_db, monkeypatch):
    plugin = SpeedtestPlugin({"id": "speedtest", "settings": dict(SpeedtestPlugin.default_settings)})
    registry.register(plugin)
    calls = []
    monkeypatch.setattr(widgets, "schedule_speedtest_widget", lambda p: calls.append(p.id))

    client.patch("/api/widgets/speedtest/settings", json={"title": "Home Internet"})

    assert calls == []


def test_summary_requires_login(unauthenticated_client, dashboard_yaml):
    registry.register(StubPlugin({}))
    response = unauthenticated_client.get("/api/widgets/stub/summary")
    assert response.status_code == 401


def test_detail_requires_login(unauthenticated_client, dashboard_yaml):
    registry.register(StubPlugin({}))
    response = unauthenticated_client.get("/api/widgets/stub/detail")
    assert response.status_code == 401


def test_update_settings_requires_login(unauthenticated_client, dashboard_yaml):
    registry.register(StubPlugin({"settings": {}}))
    response = unauthenticated_client.patch("/api/widgets/stub/settings", json={"a": 1})
    assert response.status_code == 401


def test_run_requires_login(unauthenticated_client, dashboard_yaml):
    registry.register(StubPlugin({}))
    response = unauthenticated_client.post("/api/widgets/stub/run")
    assert response.status_code == 401


def test_update_settings_rejects_member_for_network_scope_widget(member_client, dashboard_yaml, tmp_db):
    plugin = StubPlugin({"settings": {"a": 1}})
    registry.register(plugin)

    response = member_client.patch("/api/widgets/stub/settings", json={"a": 2})

    assert response.status_code == 403
    assert plugin.config["settings"] == {"a": 1}
    assert db.get_widget_settings("stub") is None


def test_update_settings_allows_member_for_personal_scope_widget(member_client, dashboard_yaml, tmp_db):
    plugin = StubPersonalPlugin({"id": "personal-stub", "settings": {"value": "default"}})
    registry.register(plugin)

    response = member_client.patch("/api/widgets/personal-stub/settings", json={"value": "mine"})

    assert response.status_code == 200
    assert response.json() == {"value": "mine"}
    # The shared plugin singleton's baseline settings are untouched — only
    # this user's own override was written.
    assert plugin.config["settings"] == {"value": "default"}
    assert db.get_widget_user_settings("member-user", "personal-stub") == {"value": "mine"}


def test_update_settings_allows_member_for_sports_widget(member_client, dashboard_yaml, tmp_db):
    registry.register(SportsPlugin({"id": "sports", "settings": dict(SportsPlugin.default_settings)}))

    response = member_client.patch("/api/widgets/sports/settings", json={"teams": [{"league": "nfl", "team": "PHI"}]})

    assert response.status_code == 200
    assert db.get_widget_user_settings("member-user", "sports")["teams"] == [{"league": "nfl", "team": "PHI"}]


def test_weather_widget_settings_are_personal_per_user(client, member_client, dashboard_yaml, tmp_db):
    registry.register(WeatherPlugin({"id": "weather", "settings": dict(WeatherPlugin.default_settings)}))

    response = member_client.patch("/api/widgets/weather/settings", json={"location_name": "Austin, TX"})
    assert response.status_code == 200
    assert db.get_widget_user_settings("member-user", "weather")["location_name"] == "Austin, TX"

    admin_response = client.patch("/api/widgets/weather/settings", json={"location_name": "Chicago, IL"})
    assert admin_response.status_code == 200
    assert db.get_widget_user_settings(TEST_USER_ID, "weather")["location_name"] == "Chicago, IL"
    assert db.get_widget_user_settings("member-user", "weather")["location_name"] == "Austin, TX"


def test_multiple_weather_widgets_have_independent_settings(client, dashboard_yaml, tmp_db):
    registry.register(WeatherPlugin({"id": "weather", "settings": dict(WeatherPlugin.default_settings)}))
    registry.register(WeatherPlugin({"id": "weather-2", "settings": dict(WeatherPlugin.default_settings)}))

    client.patch("/api/widgets/weather/settings", json={"location_name": "Austin, TX"})
    client.patch("/api/widgets/weather-2/settings", json={"location_name": "London, UK"})

    assert db.get_widget_user_settings(TEST_USER_ID, "weather")["location_name"] == "Austin, TX"
    assert db.get_widget_user_settings(TEST_USER_ID, "weather-2")["location_name"] == "London, UK"


def test_personal_scope_settings_and_summary_are_isolated_per_user(dashboard_yaml, tmp_db):
    plugin = StubPersonalPlugin({"id": "personal-stub", "settings": {"value": "default"}})
    registry.register(plugin)

    def make_client(user_id: str) -> TestClient:
        app = FastAPI()
        app.include_router(widgets.router)
        app.dependency_overrides[get_current_user] = lambda uid=user_id: {"id": uid, "role": "member"}
        app.dependency_overrides[get_current_device] = lambda: {"id": TEST_DEVICE_ID}
        return TestClient(app)

    alice, bob = make_client("alice"), make_client("bob")

    assert alice.patch("/api/widgets/personal-stub/settings", json={"value": "alice's"}).json() == {"value": "alice's"}
    assert bob.patch("/api/widgets/personal-stub/settings", json={"value": "bob's"}).json() == {"value": "bob's"}

    assert alice.get("/api/widgets/personal-stub/summary").json() == {"value": "alice's"}
    assert bob.get("/api/widgets/personal-stub/summary").json() == {"value": "bob's"}
    # Never mutated in place — with_settings() built a throwaway instance per request.
    assert plugin.config["settings"] == {"value": "default"}


def test_personal_scope_summary_is_cached_per_user(dashboard_yaml, tmp_db, monkeypatch):
    plugin = StubPersonalPlugin({"id": "personal-stub", "settings": {"value": "default"}})
    registry.register(plugin)
    db.save_widget_user_settings("alice", "personal-stub", {"value": "alice's"})

    lookups: list[str] = []
    original = db.get_widget_user_settings

    def counting_lookup(user_id: str, widget_id: str):
        lookups.append(user_id)
        return original(user_id, widget_id)

    monkeypatch.setattr(scoping, "get_widget_user_settings", counting_lookup)

    app = FastAPI()
    app.include_router(widgets.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "alice", "role": "member"}
    app.dependency_overrides[get_current_device] = lambda: {"id": TEST_DEVICE_ID}
    alice_client = TestClient(app)

    assert alice_client.get("/api/widgets/personal-stub/summary").json() == {"value": "alice's"}
    assert alice_client.get("/api/widgets/personal-stub/summary").json() == {"value": "alice's"}

    # Second request was served from cache — no repeat per-user settings lookup.
    assert lookups == ["alice"]


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


def test_run_triggers_speedtest_and_returns_fresh_detail(client, dashboard_yaml, tmp_db, monkeypatch):
    plugin = SpeedtestPlugin({"id": "speedtest", "settings": dict(SpeedtestPlugin.default_settings)})
    registry.register(plugin)

    async def fake_run_speedtest_widget(run_plugin):
        assert run_plugin is plugin
        db.record_speedtest_run(
            run_plugin.id, download_mbps=250.0, upload_mbps=25.0, ping_ms=8.0, server_name="Fresh ISP"
        )

    monkeypatch.setattr(widgets, "run_speedtest_widget", fake_run_speedtest_widget)

    response = client.post("/api/widgets/speedtest/run")

    assert response.status_code == 200
    assert response.json()["server_name"] == "Fresh ISP"


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

    response = client.get("/api/widgets?breakpoint=wide")

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


def test_add_widget_schedules_speedtest_interval_job(client, dashboard_yaml, tmp_db):
    try:
        response = client.post(
            "/api/widgets",
            json={"type": "speedtest", "layout": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}},
        )
        widget_id = response.json()["id"]

        assert scheduler_module.scheduler.get_job(f"speedtest:{widget_id}") is not None
    finally:
        scheduler_module.scheduler.remove_all_jobs()


def test_add_widget_requires_login(unauthenticated_client, dashboard_yaml, tmp_db):
    response = unauthenticated_client.post(
        "/api/widgets",
        json={"type": "clock", "layout": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}},
    )
    assert response.status_code == 401


def test_add_widget_rejects_member_for_network_scope_widget_type(member_client, dashboard_yaml, tmp_db):
    response = member_client.post(
        "/api/widgets",
        json={"type": "clock", "layout": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}},
    )
    assert response.status_code == 403


def test_add_widget_allows_member_for_personal_scope_widget_type(member_client, dashboard_yaml, tmp_db):
    response = member_client.post(
        "/api/widgets",
        json={"type": "rss", "layout": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}},
    )
    assert response.status_code == 200


def test_add_widget_returns_400_for_unknown_type(client, dashboard_yaml, tmp_db):
    response = client.post(
        "/api/widgets",
        json={"type": "nonexistent", "layout": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}},
    )

    assert response.status_code == 400


def test_remove_widget_returns_404_for_unregistered_widget(client, dashboard_yaml, tmp_db):
    response = client.delete("/api/widgets/nonexistent")
    assert response.status_code == 404


def test_remove_widget_requires_login(unauthenticated_client, dashboard_yaml, tmp_db):
    registry.register(StubPlugin({}))
    response = unauthenticated_client.delete("/api/widgets/stub")
    assert response.status_code == 401


def test_remove_widget_hides_network_scope_widget_for_member(member_client, dashboard_yaml, tmp_db):
    # "stub" is a dashboard.yaml widget with no custom_widgets row, so it's
    # never "owned" by any (user, device) pair — deleting it always hides it
    # from just the requester's own list rather than deleting it outright.
    # The admin-only gate only applies to the full-delete path (an owned
    # widget's creator lacking write access), which a shared default never
    # reaches — any household member may declutter their own screen.
    registry.register(StubPlugin({}))

    response = member_client.delete("/api/widgets/stub")

    assert response.status_code == 200
    assert response.json() == {"status": "hidden"}
    assert registry.get("stub") is not None


def test_remove_widget_owned_by_a_different_device_is_hidden_not_deleted(client, dashboard_yaml, tmp_db):
    db.save_custom_widget(
        "personal-stub",
        "personal-stub",
        {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1},
        None,
        "other-user",
        "other-device",
    )
    registry.register(StubPersonalPlugin({"id": "personal-stub", "settings": {}}))

    response = client.delete("/api/widgets/personal-stub")

    assert response.status_code == 200
    assert response.json() == {"status": "hidden"}
    assert registry.get("personal-stub") is not None
    assert db.hidden_widget_ids(TEST_USER_ID, TEST_DEVICE_ID) == {"personal-stub"}


def test_remove_widget_allows_member_for_personal_scope_widget(member_client, dashboard_yaml, tmp_db):
    registry.register(StubPersonalPlugin({"id": "personal-stub", "settings": {}}))
    response = member_client.delete("/api/widgets/personal-stub")
    assert response.status_code == 200


def test_remove_widget_rejects_the_owner_when_they_lack_write_access(client, dashboard_yaml, tmp_db):
    # Not reachable through the normal add-widget flow today (a member can
    # never create a network-scope custom widget in the first place), but
    # remove_widget still runs require_write_access on the owned-delete path
    # — exercise it directly.
    db.save_custom_widget(
        "stub", "stub", {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}, None, "member-user", TEST_DEVICE_ID
    )
    registry.register(StubPlugin({}))
    app = FastAPI()
    app.include_router(widgets.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "member-user", "role": "member"}
    app.dependency_overrides[get_current_device] = lambda: {"id": TEST_DEVICE_ID}
    member_owner_client = TestClient(app)

    response = member_owner_client.delete("/api/widgets/stub")

    assert response.status_code == 403
    assert registry.get("stub") is not None


def test_remove_widget_hides_yaml_widget_and_leaves_it_registered(client, dashboard_yaml, tmp_db):
    plugin = StubPlugin({})
    registry.register(plugin)

    response = client.delete("/api/widgets/stub")

    assert response.status_code == 200
    assert response.json() == {"status": "hidden"}
    assert registry.get("stub") is plugin
    assert db.hidden_widget_ids(TEST_USER_ID, TEST_DEVICE_ID) == {"stub"}


def test_remove_widget_hides_yaml_widget_from_list(client, dashboard_yaml, tmp_db):
    registry.register(StubPlugin({}))

    client.delete("/api/widgets/stub")

    response = client.get("/api/widgets?breakpoint=wide")
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
    assert db.hidden_widget_ids(TEST_USER_ID, TEST_DEVICE_ID) == set()


def test_remove_widget_deletes_photo_index_rows(client, dashboard_yaml, tmp_db):
    try:
        add_response = client.post(
            "/api/widgets",
            json={"type": "photos", "layout": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1}},
        )
        widget_id = add_response.json()["id"]
        generation = db.begin_photo_index_scan(widget_id)
        db.upsert_photo_index_chunk(widget_id, generation, ["a.jpg"], 0)
        db.finish_photo_index_scan(widget_id, generation)
        assert db.photo_index_photo_ids(widget_id) == ["a.jpg"]

        response = client.delete(f"/api/widgets/{widget_id}")

        assert response.status_code == 200
        assert db.photo_index_photo_ids(widget_id) == []
        assert db.photo_index_status(widget_id) is None
    finally:
        scheduler_module.scheduler.remove_all_jobs()


def test_remove_widget_deletes_per_user_settings(client, dashboard_yaml, tmp_db):
    # Registered as an owned custom widget (matching how a real UI-added
    # personal widget is created) so DELETE takes the full-delete path
    # rather than just hiding it — see app.api.widgets.remove_widget.
    db.save_custom_widget(
        "personal-stub",
        "personal-stub",
        {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1},
        None,
        TEST_USER_ID,
        TEST_DEVICE_ID,
    )
    registry.register(StubPersonalPlugin({"id": "personal-stub", "settings": {}}))
    db.save_widget_user_settings(TEST_USER_ID, "personal-stub", {"value": "mine"})

    response = client.delete("/api/widgets/personal-stub")

    assert response.status_code == 200
    assert db.get_widget_user_settings(TEST_USER_ID, "personal-stub") is None


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


def test_get_device_settings_returns_empty_when_unset(client, dashboard_yaml, tmp_db):
    registry.register(StubDeviceOverridablePlugin({"settings": {"value": "default"}}))

    response = client.get("/api/widgets/device-stub/device-settings")

    assert response.status_code == 200
    assert response.json() == {}


def test_get_device_settings_returns_404_for_unregistered_widget(client, dashboard_yaml):
    response = client.get("/api/widgets/nonexistent/device-settings")
    assert response.status_code == 404


def test_update_device_settings_rejects_keys_not_device_overridable(client, dashboard_yaml, tmp_db):
    registry.register(StubDeviceOverridablePlugin({"settings": {"value": "default"}}))

    response = client.patch("/api/widgets/device-stub/device-settings", json={"other": "nope"})

    assert response.status_code == 400
    assert db.get_widget_device_settings(TEST_DEVICE_ID, "device-stub") is None


def test_update_device_settings_persists_and_returns_merged_override(client, dashboard_yaml, tmp_db):
    registry.register(StubDeviceOverridablePlugin({"settings": {"value": "default"}}))

    response = client.patch("/api/widgets/device-stub/device-settings", json={"value": "overridden"})

    assert response.status_code == 200
    assert response.json() == {"value": "overridden"}
    assert db.get_widget_device_settings(TEST_DEVICE_ID, "device-stub") == {"value": "overridden"}


def test_update_device_settings_invalidates_cached_summary_and_detail(client, dashboard_yaml, tmp_db):
    plugin = StubDeviceOverridablePlugin({"settings": {"value": "default"}})
    registry.register(plugin)
    assert client.get("/api/widgets/device-stub/summary").json() == {"value": "default"}

    client.patch("/api/widgets/device-stub/device-settings", json={"value": "overridden"})

    assert client.get("/api/widgets/device-stub/summary").json() == {"value": "overridden"}


def test_device_settings_are_isolated_between_devices(dashboard_yaml, tmp_db):
    plugin = StubDeviceOverridablePlugin({"settings": {"value": "default"}})
    registry.register(plugin)

    def make_client(device_id: str) -> TestClient:
        app = FastAPI()
        app.include_router(widgets.router)
        app.dependency_overrides[get_current_user] = lambda: {"id": TEST_USER_ID, "role": "admin"}
        app.dependency_overrides[get_current_device] = lambda did=device_id: {"id": did}
        return TestClient(app)

    device_a, device_b = make_client("device-a"), make_client("device-b")

    device_a.patch("/api/widgets/device-stub/device-settings", json={"value": "a's value"})

    assert device_a.get("/api/widgets/device-stub/summary").json() == {"value": "a's value"}
    assert device_b.get("/api/widgets/device-stub/summary").json() == {"value": "default"}
    # Never mutated in place — with_settings() built a throwaway instance per request.
    assert plugin.config["settings"] == {"value": "default"}


def test_updating_network_default_invalidates_every_devices_cache(dashboard_yaml, tmp_db):
    plugin = StubDeviceOverridablePlugin({"settings": {"value": "default"}})
    registry.register(plugin)

    def make_client(device_id: str) -> TestClient:
        app = FastAPI()
        app.include_router(widgets.router)
        app.dependency_overrides[get_current_user] = lambda: {"id": TEST_USER_ID, "role": "admin"}
        app.dependency_overrides[get_current_device] = lambda did=device_id: {"id": did}
        return TestClient(app)

    device_a, device_b = make_client("device-a"), make_client("device-b")
    # Populate a cached summary for both devices under the old default.
    device_a.get("/api/widgets/device-stub/summary")
    device_b.get("/api/widgets/device-stub/summary")

    device_a.patch("/api/widgets/device-stub/settings", json={"value": "new-default"})

    assert device_a.get("/api/widgets/device-stub/summary").json() == {"value": "new-default"}
    assert device_b.get("/api/widgets/device-stub/summary").json() == {"value": "new-default"}


def test_updating_personal_settings_invalidates_every_devices_cache_for_that_user(dashboard_yaml, tmp_db):
    plugin = StubPersonalDeviceOverridablePlugin({"settings": {"value": "default"}})
    registry.register(plugin)

    def make_client(device_id: str) -> TestClient:
        app = FastAPI()
        app.include_router(widgets.router)
        app.dependency_overrides[get_current_user] = lambda: {"id": TEST_USER_ID, "role": "admin"}
        app.dependency_overrides[get_current_device] = lambda did=device_id: {"id": did}
        return TestClient(app)

    device_a, device_b = make_client("device-a"), make_client("device-b")
    # Populate a cached summary for both of this user's devices under the old value.
    device_a.get("/api/widgets/personal-device-stub/summary")
    device_b.get("/api/widgets/personal-device-stub/summary")

    device_a.patch("/api/widgets/personal-device-stub/settings", json={"value": "mine"})

    assert device_a.get("/api/widgets/personal-device-stub/summary").json() == {"value": "mine"}
    assert device_b.get("/api/widgets/personal-device-stub/summary").json() == {"value": "mine"}


def test_clear_device_settings_falls_back_to_household_default(client, dashboard_yaml, tmp_db):
    registry.register(StubDeviceOverridablePlugin({"settings": {"value": "default"}}))
    client.patch("/api/widgets/device-stub/device-settings", json={"value": "overridden"})
    assert client.get("/api/widgets/device-stub/summary").json() == {"value": "overridden"}

    response = client.delete("/api/widgets/device-stub/device-settings")

    assert response.status_code == 200
    assert db.get_widget_device_settings(TEST_DEVICE_ID, "device-stub") is None
    assert client.get("/api/widgets/device-stub/summary").json() == {"value": "default"}


def test_remove_widget_deletes_device_settings(client, dashboard_yaml, tmp_db):
    db.save_custom_widget(
        "device-stub",
        "device-stub",
        {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1},
        None,
        TEST_USER_ID,
        TEST_DEVICE_ID,
    )
    registry.register(StubDeviceOverridablePlugin({"settings": {"value": "default"}}))
    db.save_widget_device_settings(TEST_DEVICE_ID, "device-stub", {"value": "mine"})

    response = client.delete("/api/widgets/device-stub")

    assert response.status_code == 200
    assert db.get_widget_device_settings(TEST_DEVICE_ID, "device-stub") is None


def test_update_settings_rejects_connection_keys_for_network_integration_plugins(client, tmp_db):
    settings = {**PiholePlugin.network_default_settings, **PiholePlugin.default_settings}
    registry.register(PiholePlugin({"id": "pihole", "settings": settings}))

    response = client.patch("/api/widgets/pihole/settings", json={"host": "new.local"})

    assert response.status_code == 400
    assert "network-settings" in response.json()["detail"]
    # The rejected key is never applied, even though it's part of the payload.
    assert registry.get("pihole").config["settings"]["host"] == ""


def test_update_settings_container_re_resolves_on_reference_change(client, tmp_db):
    db.save_network_integration(
        "container-docker", "container", "Docker", {**ContainerPlugin.network_default_settings, "host": "docker.local"}
    )
    db.save_network_integration(
        "container-podman", "container", "Podman", {**ContainerPlugin.network_default_settings, "host": "podman.local"}
    )
    settings = {
        "network_integration_id": "container-docker",
        **ContainerPlugin.network_default_settings,
        "host": "docker.local",
    }
    registry.register(ContainerPlugin({"id": "container-a", "settings": settings}))

    response = client.patch("/api/widgets/container-a/settings", json={"network_integration_id": "container-podman"})

    assert response.status_code == 200
    assert response.json()["network_integration_id"] == "container-podman"
    assert response.json()["host"] == "podman.local"
    assert registry.get("container-a").config["settings"]["host"] == "podman.local"
    # Only the display-only key is persisted to widget_settings — connection
    # fields stay live-only, re-resolved from the integration row on read.
    assert db.get_widget_settings("container-a") == {"network_integration_id": "container-podman"}
