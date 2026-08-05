from __future__ import annotations

from datetime import datetime

import pytest

import app.scheduler as scheduler_module
from app import config
from app.plugins.ai_insights.plugin import AIInsightsPlugin
from app.plugins.base import registry
from app.plugins.photos.plugin import PhotosPlugin
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
