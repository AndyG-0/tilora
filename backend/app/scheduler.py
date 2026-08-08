"""APScheduler wiring: runs each AI-capable widget's prompt on its cron."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.ai import assistant
from app.config import settings
from app.i18n import DEFAULT_LOCALE, LANGUAGE_NAMES
from app.integrations import speedtest_runner, track17_client
from app.plugins.ai_insights.plugin import AIInsightsPlugin
from app.plugins.base import registry
from app.plugins.packages.plugin import PackagesPlugin
from app.plugins.photos.indexer import index_photos
from app.plugins.photos.plugin import PhotosPlugin
from app.plugins.speedtest.plugin import SpeedtestPlugin
from app.plugins.weather.plugin import WeatherPlugin
from app.storage import db
from app.storage.cache import cache

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

# The Alert plugin's fixed widget id (see app.plugins.alert.plugin) — severe
# weather signals are raised onto it directly, the same way POST /api/alerts
# does, rather than through the AI tool-calling layer.
ALERT_WIDGET_ID = "alert"
_SEVERE_WEATHER_ALERT_EXPIRES_MINUTES = 360

# 17Track's free tier is rate-limited, so package status/ETA is refreshed on
# a slow interval rather than on every dashboard poll — see PackagesPlugin.
_PACKAGE_REFRESH_INTERVAL_MINUTES = 90


async def run_ai_widget(plugin: AIInsightsPlugin) -> None:
    try:
        system_prompt = None
        if plugin.language != DEFAULT_LOCALE:
            language_name = LANGUAGE_NAMES.get(plugin.language, plugin.language)
            system_prompt = f"Respond in {language_name}."
        text = await assistant.ask(plugin.prompt, system_prompt=system_prompt, allowed_widget_ids=plugin.topics or None)
        await asyncio.to_thread(db.record_ai_run, plugin.id, {"text": text})
        logger.info("AI widget '%s' ran successfully", plugin.id)
    except Exception:
        logger.exception("AI widget '%s' failed to run", plugin.id)


def schedule_ai_widget(plugin: AIInsightsPlugin) -> None:
    scheduler.add_job(
        run_ai_widget,
        trigger=CronTrigger.from_crontab(plugin.cron),
        args=[plugin],
        id=f"ai-widget:{plugin.id}",
        replace_existing=True,
    )


def schedule_ai_widgets() -> None:
    for plugin in registry.all():
        if isinstance(plugin, AIInsightsPlugin):
            schedule_ai_widget(plugin)


def schedule_photo_index(plugin: PhotosPlugin, run_immediately: bool = True) -> None:
    """Registers/replaces plugin's interval index-refresh job.

    Called at startup for every configured photos widget, when a photos
    widget is added, and whenever its source-relevant settings change —
    `run_immediately` (default True) makes the first scan happen right
    away instead of waiting a full interval. Re-registering also resets
    the interval clock from "now", avoiding a near-immediate duplicate
    scan right after a manual one.
    """
    kwargs = {"next_run_time": datetime.now()} if run_immediately else {}
    scheduler.add_job(
        index_photos,
        trigger=IntervalTrigger(seconds=plugin.index_refresh_seconds),
        args=[plugin],
        id=f"photo-index:{plugin.id}",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        **kwargs,
    )


def schedule_photo_index_widgets() -> None:
    for plugin in registry.all():
        if isinstance(plugin, PhotosPlugin):
            schedule_photo_index(plugin)


async def run_speedtest_widget(plugin: SpeedtestPlugin) -> None:
    try:
        result = await asyncio.to_thread(speedtest_runner.run_speedtest)
        await asyncio.to_thread(db.record_speedtest_run, plugin.id, **result)
        logger.info("Speedtest widget '%s' ran successfully", plugin.id)
    except Exception:
        logger.exception("Speedtest widget '%s' failed to run", plugin.id)


def schedule_speedtest_widget(plugin: SpeedtestPlugin) -> None:
    scheduler.add_job(
        run_speedtest_widget,
        trigger=IntervalTrigger(minutes=plugin.interval_minutes),
        args=[plugin],
        id=f"speedtest:{plugin.id}",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )


def schedule_speedtest_widgets() -> None:
    for plugin in registry.all():
        if isinstance(plugin, SpeedtestPlugin):
            schedule_speedtest_widget(plugin)


async def run_severe_weather_check(plugin: WeatherPlugin) -> None:
    if not plugin.config["settings"].get("severe_weather_alerts", True):
        return
    if registry.get(ALERT_WIDGET_ID) is None:
        logger.debug("No Alert widget registered — skipping severe weather check for '%s'", plugin.id)
        return

    try:
        signals = await plugin.get_severe_weather_signals()
    except Exception:
        logger.exception("Severe weather check failed for widget '%s'", plugin.id)
        return

    for signal in signals:
        already_seen = await asyncio.to_thread(db.has_seen_severe_weather_alert, plugin.id, signal["key"])
        if already_seen:
            continue
        await asyncio.to_thread(
            db.create_alert,
            ALERT_WIDGET_ID,
            signal["message"],
            signal["severity"],
            _SEVERE_WEATHER_ALERT_EXPIRES_MINUTES,
        )
        await asyncio.to_thread(db.mark_severe_weather_alert_seen, plugin.id, signal["key"])
        cache.delete(f"summary:{ALERT_WIDGET_ID}")
        cache.delete(f"detail:{ALERT_WIDGET_ID}")
        logger.info("Severe weather alert raised for widget '%s': %s", plugin.id, signal["key"])


def schedule_severe_weather_widget(plugin: WeatherPlugin) -> None:
    scheduler.add_job(
        run_severe_weather_check,
        trigger=IntervalTrigger(minutes=15),
        args=[plugin],
        id=f"severe-weather:{plugin.id}",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )


def schedule_severe_weather_widgets() -> None:
    for plugin in registry.all():
        if isinstance(plugin, WeatherPlugin):
            schedule_severe_weather_widget(plugin)


async def run_package_refresh(plugin: PackagesPlugin) -> None:
    api_key = settings.track17_api_key
    if not api_key:
        return

    packages = await asyncio.to_thread(db.list_packages, plugin.id)
    pending = [p for p in packages if not p["delivered"]]
    if not pending:
        return

    try:
        results = await track17_client.get_track_info(api_key, [p["tracking_number"] for p in pending])
    except track17_client.Track17Error:
        logger.exception("Package refresh failed for widget '%s'", plugin.id)
        return

    for package in pending:
        info = results.get(package["tracking_number"])
        if info is None:
            continue
        await asyncio.to_thread(
            db.update_package_status,
            package["id"],
            carrier=info.get("carrier"),
            status=info.get("status"),
            last_event=info.get("last_event"),
            eta_date=info.get("eta_date"),
            delivered=info.get("delivered"),
        )

    cache.delete_prefix(f"summary:{plugin.id}:")
    cache.delete_prefix(f"detail:{plugin.id}:")
    logger.info("Package widget '%s' refreshed %d pending package(s)", plugin.id, len(pending))


def schedule_package_refresh(plugin: PackagesPlugin) -> None:
    scheduler.add_job(
        run_package_refresh,
        trigger=IntervalTrigger(minutes=_PACKAGE_REFRESH_INTERVAL_MINUTES),
        args=[plugin],
        id=f"package-refresh:{plugin.id}",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )


def schedule_package_refresh_widgets() -> None:
    for plugin in registry.all():
        if isinstance(plugin, PackagesPlugin):
            schedule_package_refresh(plugin)


def unschedule_widget(widget_id: str) -> None:
    """No-op for any job the widget never had (e.g. not an AI/photos/speedtest widget)."""
    for job_id in (
        f"ai-widget:{widget_id}",
        f"photo-index:{widget_id}",
        f"speedtest:{widget_id}",
        f"severe-weather:{widget_id}",
        f"package-refresh:{widget_id}",
    ):
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
