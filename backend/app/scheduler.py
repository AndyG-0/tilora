"""APScheduler wiring: runs each AI-capable widget's prompt on its cron."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.ai import assistant
from app.plugins.ai_insights.plugin import AIInsightsPlugin
from app.plugins.base import registry
from app.plugins.photos.indexer import index_photos
from app.plugins.photos.plugin import PhotosPlugin
from app.storage import db

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def run_ai_widget(plugin: AIInsightsPlugin) -> None:
    try:
        text = await assistant.ask(plugin.prompt, allowed_widget_ids=plugin.topics or None)
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


def unschedule_widget(widget_id: str) -> None:
    """No-op for any job the widget never had (e.g. not an AI/photos widget)."""
    for job_id in (f"ai-widget:{widget_id}", f"photo-index:{widget_id}"):
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
