from __future__ import annotations

from datetime import datetime

import pytest

import app.scheduler as scheduler_module
from app import config
from app.plugins.ai_insights.plugin import AIInsightsPlugin
from app.plugins.base import registry
from app.plugins.packages.plugin import PackagesPlugin
from app.plugins.photos.plugin import PhotosPlugin
from app.plugins.speedtest.plugin import SpeedtestPlugin
from app.plugins.weather.plugin import WeatherPlugin
from app.storage import db


@pytest.fixture
def dashboard_yaml(tmp_path, monkeypatch):
    path = tmp_path / "dashboard.yaml"
    path.write_text("widgets: []\n")
    monkeypatch.setattr(config, "DASHBOARD_CONFIG_PATH", path)
    return path


def make_ai_plugin() -> AIInsightsPlugin:
    return AIInsightsPlugin({"id": "ai-insights", "settings": {"cron": "30 6 * * *", "prompt": "Say hello"}})


def make_photos_plugin(**settings) -> PhotosPlugin:
    return PhotosPlugin({"id": "photos", "settings": {"directory": "/tmp/does-not-matter", **settings}})


def make_speedtest_plugin(**settings) -> SpeedtestPlugin:
    return SpeedtestPlugin({"id": "speedtest", "settings": {"title": "Speedtest", "interval_minutes": 60, **settings}})


def make_packages_plugin(**settings) -> PackagesPlugin:
    return PackagesPlugin({"id": "packages", "settings": {"title": "Packages", **settings}})


def test_schedule_ai_widgets_only_schedules_ai_insights_plugins():
    registry.register(make_ai_plugin())
    registry.register(WeatherPlugin({"id": "weather", "settings": {"latitude": 0, "longitude": 0}}))

    scheduler_module.schedule_ai_widgets()
    try:
        job_ids = {job.id for job in scheduler_module.scheduler.get_jobs()}
        assert job_ids == {"ai-widget:ai-insights"}
    finally:
        scheduler_module.scheduler.remove_all_jobs()


async def test_run_ai_widget_records_successful_run(tmp_db, dashboard_yaml, monkeypatch):
    plugin = make_ai_plugin()
    registry.register(plugin)

    async def fake_run_prompt(self, prompt, max_tool_rounds=4, system_prompt=None):
        return "Sunny and 75."

    monkeypatch.setattr("app.ai.provider.AIProvider.run_prompt", fake_run_prompt)

    await scheduler_module.run_ai_widget(plugin)

    latest = db.latest_ai_run(plugin.id)
    assert latest["text"] == "Sunny and 75."


async def test_run_ai_widget_passes_topics_as_allowed_widget_ids(tmp_db, dashboard_yaml, monkeypatch):
    plugin = AIInsightsPlugin(
        {
            "id": "ai-insights",
            "settings": {"cron": "30 6 * * *", "prompt": "Say hello", "topics": ["calendar", "weather"]},
        }
    )
    registry.register(plugin)
    captured = {}

    async def fake_ask(text, system_prompt=None, user=None, device=None, allowed_widget_ids=None):
        captured["allowed_widget_ids"] = allowed_widget_ids
        return "Sunny and 75."

    monkeypatch.setattr(scheduler_module.assistant, "ask", fake_ask)

    await scheduler_module.run_ai_widget(plugin)

    assert captured["allowed_widget_ids"] == ["calendar", "weather"]


async def test_run_ai_widget_passes_none_when_no_topics_selected(tmp_db, dashboard_yaml, monkeypatch):
    plugin = make_ai_plugin()
    registry.register(plugin)
    captured = {}

    async def fake_ask(text, system_prompt=None, user=None, device=None, allowed_widget_ids=None):
        captured["allowed_widget_ids"] = allowed_widget_ids
        return "Sunny and 75."

    monkeypatch.setattr(scheduler_module.assistant, "ask", fake_ask)

    await scheduler_module.run_ai_widget(plugin)

    assert captured["allowed_widget_ids"] is None


async def test_run_ai_widget_passes_no_system_prompt_for_default_language(tmp_db, dashboard_yaml, monkeypatch):
    plugin = make_ai_plugin()
    registry.register(plugin)
    captured = {}

    async def fake_ask(text, system_prompt=None, user=None, device=None, allowed_widget_ids=None):
        captured["system_prompt"] = system_prompt
        return "Sunny and 75."

    monkeypatch.setattr(scheduler_module.assistant, "ask", fake_ask)

    await scheduler_module.run_ai_widget(plugin)

    assert captured["system_prompt"] is None


async def test_run_ai_widget_passes_locale_instruction_for_configured_language(tmp_db, dashboard_yaml, monkeypatch):
    plugin = AIInsightsPlugin(
        {
            "id": "ai-insights",
            "settings": {"cron": "30 6 * * *", "prompt": "Say hello", "language": "es"},
        }
    )
    registry.register(plugin)
    captured = {}

    async def fake_ask(text, system_prompt=None, user=None, device=None, allowed_widget_ids=None):
        captured["system_prompt"] = system_prompt
        return "Sunny and 75."

    monkeypatch.setattr(scheduler_module.assistant, "ask", fake_ask)

    await scheduler_module.run_ai_widget(plugin)

    assert captured["system_prompt"] == "Respond in Spanish."


async def test_run_ai_widget_swallows_exceptions(tmp_db, monkeypatch):
    plugin = make_ai_plugin()
    registry.register(plugin)

    async def failing_run_prompt(self, prompt, max_tool_rounds=4):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr("app.ai.provider.AIProvider.run_prompt", failing_run_prompt)

    await scheduler_module.run_ai_widget(plugin)  # must not raise

    assert db.latest_ai_run(plugin.id) is None


def test_schedule_photo_index_widgets_only_schedules_photos_plugins():
    registry.register(make_photos_plugin())
    registry.register(WeatherPlugin({"id": "weather", "settings": {"latitude": 0, "longitude": 0}}))

    scheduler_module.schedule_photo_index_widgets()
    try:
        job_ids = {job.id for job in scheduler_module.scheduler.get_jobs()}
        assert job_ids == {"photo-index:photos"}
    finally:
        scheduler_module.scheduler.remove_all_jobs()


def test_schedule_photo_index_runs_immediately_by_default():
    plugin = make_photos_plugin()

    scheduler_module.schedule_photo_index(plugin)
    try:
        job = scheduler_module.scheduler.get_job("photo-index:photos")
        now = datetime.now(job.next_run_time.tzinfo)
        assert abs((job.next_run_time - now).total_seconds()) < 5
    finally:
        scheduler_module.scheduler.remove_all_jobs()


def test_schedule_photo_index_can_defer_first_run(monkeypatch):
    plugin = make_photos_plugin(index_refresh_seconds=3600)
    seen_kwargs = {}
    original_add_job = scheduler_module.scheduler.add_job

    def spy_add_job(*args, **kwargs):
        seen_kwargs.update(kwargs)
        return original_add_job(*args, **kwargs)

    monkeypatch.setattr(scheduler_module.scheduler, "add_job", spy_add_job)

    scheduler_module.schedule_photo_index(plugin, run_immediately=False)
    try:
        assert "next_run_time" not in seen_kwargs
    finally:
        scheduler_module.scheduler.remove_all_jobs()


def test_unschedule_widget_removes_ai_and_photo_index_jobs():
    schedule_ai = make_ai_plugin()
    schedule_photos = make_photos_plugin()
    scheduler_module.schedule_ai_widget(schedule_ai)
    scheduler_module.schedule_photo_index(schedule_photos)
    try:
        scheduler_module.unschedule_widget("ai-insights")
        scheduler_module.unschedule_widget("photos")

        assert scheduler_module.scheduler.get_job("ai-widget:ai-insights") is None
        assert scheduler_module.scheduler.get_job("photo-index:photos") is None
    finally:
        scheduler_module.scheduler.remove_all_jobs()


def test_unschedule_widget_is_a_noop_for_unknown_widget():
    scheduler_module.unschedule_widget("does-not-exist")  # must not raise


def test_schedule_speedtest_widgets_only_schedules_speedtest_plugins():
    registry.register(make_speedtest_plugin())
    registry.register(WeatherPlugin({"id": "weather", "settings": {"latitude": 0, "longitude": 0}}))

    scheduler_module.schedule_speedtest_widgets()
    try:
        job_ids = {job.id for job in scheduler_module.scheduler.get_jobs()}
        assert job_ids == {"speedtest:speedtest"}
    finally:
        scheduler_module.scheduler.remove_all_jobs()


def test_schedule_speedtest_widget_uses_interval_minutes_setting():
    plugin = make_speedtest_plugin(interval_minutes=15)

    scheduler_module.schedule_speedtest_widget(plugin)
    try:
        job = scheduler_module.scheduler.get_job("speedtest:speedtest")
        assert job.trigger.interval.total_seconds() == 15 * 60
    finally:
        scheduler_module.scheduler.remove_all_jobs()


async def test_run_speedtest_widget_records_successful_run(tmp_db, monkeypatch):
    plugin = make_speedtest_plugin()

    def fake_run_speedtest():
        return {"download_mbps": 300.0, "upload_mbps": 30.0, "ping_ms": 5.0, "server_name": "Fast ISP"}

    monkeypatch.setattr(scheduler_module.speedtest_runner, "run_speedtest", fake_run_speedtest)

    await scheduler_module.run_speedtest_widget(plugin)

    latest = db.latest_speedtest_run(plugin.id)
    assert latest["server_name"] == "Fast ISP"
    assert latest["download_mbps"] == 300.0


async def test_run_speedtest_widget_swallows_exceptions(tmp_db, monkeypatch):
    plugin = make_speedtest_plugin()

    def failing_run_speedtest():
        raise RuntimeError("network unreachable")

    monkeypatch.setattr(scheduler_module.speedtest_runner, "run_speedtest", failing_run_speedtest)

    await scheduler_module.run_speedtest_widget(plugin)  # must not raise

    assert db.latest_speedtest_run(plugin.id) is None


def test_unschedule_widget_removes_speedtest_job():
    plugin = make_speedtest_plugin()
    scheduler_module.schedule_speedtest_widget(plugin)
    try:
        scheduler_module.unschedule_widget("speedtest")

        assert scheduler_module.scheduler.get_job("speedtest:speedtest") is None
    finally:
        scheduler_module.scheduler.remove_all_jobs()


def test_schedule_package_refresh_widgets_only_schedules_packages_plugins():
    registry.register(make_packages_plugin())
    registry.register(WeatherPlugin({"id": "weather", "settings": {"latitude": 0, "longitude": 0}}))

    scheduler_module.schedule_package_refresh_widgets()
    try:
        job_ids = {job.id for job in scheduler_module.scheduler.get_jobs()}
        assert job_ids == {"package-refresh:packages"}
    finally:
        scheduler_module.scheduler.remove_all_jobs()


def test_schedule_package_refresh_uses_90_minute_interval():
    plugin = make_packages_plugin()

    scheduler_module.schedule_package_refresh(plugin)
    try:
        job = scheduler_module.scheduler.get_job("package-refresh:packages")
        assert job.trigger.interval.total_seconds() == 90 * 60
    finally:
        scheduler_module.scheduler.remove_all_jobs()


async def test_run_package_refresh_noop_without_api_key(tmp_db, monkeypatch):
    monkeypatch.setattr(scheduler_module.settings, "track17_api_key", None)
    plugin = make_packages_plugin()
    package = db.add_package(plugin.id, "alice", "1Z999AA1")

    await scheduler_module.run_package_refresh(plugin)

    assert db.get_package(package["id"])["status"] is None


async def test_run_package_refresh_noop_when_no_pending_packages(tmp_db, monkeypatch):
    monkeypatch.setattr(scheduler_module.settings, "track17_api_key", "test-key")
    plugin = make_packages_plugin()

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("get_track_info should not be called with nothing pending")

    monkeypatch.setattr(scheduler_module.track17_client, "get_track_info", fail_if_called)

    await scheduler_module.run_package_refresh(plugin)  # must not raise


async def test_run_package_refresh_updates_pending_packages(tmp_db, monkeypatch):
    monkeypatch.setattr(scheduler_module.settings, "track17_api_key", "test-key")
    plugin = make_packages_plugin()
    package = db.add_package(plugin.id, "alice", "1Z999AA1")

    async def fake_get_track_info(api_key, tracking_numbers):
        assert api_key == "test-key"
        assert tracking_numbers == ["1Z999AA1"]
        return {
            "1Z999AA1": {
                "carrier": "UPS",
                "status": "InTransit",
                "last_event": "Departed facility",
                "eta_date": "2026-08-10",
                "delivered": False,
            }
        }

    monkeypatch.setattr(scheduler_module.track17_client, "get_track_info", fake_get_track_info)

    await scheduler_module.run_package_refresh(plugin)

    updated = db.get_package(package["id"])
    assert updated["carrier"] == "UPS"
    assert updated["status"] == "InTransit"
    assert updated["eta_date"] == "2026-08-10"


async def test_run_package_refresh_skips_packages_17track_returns_nothing_for(tmp_db, monkeypatch):
    monkeypatch.setattr(scheduler_module.settings, "track17_api_key", "test-key")
    plugin = make_packages_plugin()
    package = db.add_package(plugin.id, "alice", "1Z999AA1")

    async def fake_get_track_info(api_key, tracking_numbers):
        return {}

    monkeypatch.setattr(scheduler_module.track17_client, "get_track_info", fake_get_track_info)

    await scheduler_module.run_package_refresh(plugin)  # must not raise

    assert db.get_package(package["id"])["status"] is None


async def test_run_package_refresh_swallows_track17_errors(tmp_db, monkeypatch):
    monkeypatch.setattr(scheduler_module.settings, "track17_api_key", "test-key")
    plugin = make_packages_plugin()
    db.add_package(plugin.id, "alice", "1Z999AA1")

    async def failing_get_track_info(api_key, tracking_numbers):
        raise scheduler_module.track17_client.Track17Error("boom")

    monkeypatch.setattr(scheduler_module.track17_client, "get_track_info", failing_get_track_info)

    await scheduler_module.run_package_refresh(plugin)  # must not raise


def test_unschedule_widget_removes_package_refresh_job():
    plugin = make_packages_plugin()
    scheduler_module.schedule_package_refresh(plugin)
    try:
        scheduler_module.unschedule_widget("packages")

        assert scheduler_module.scheduler.get_job("package-refresh:packages") is None
    finally:
        scheduler_module.scheduler.remove_all_jobs()
