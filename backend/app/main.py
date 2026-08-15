from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin as admin_api,
)
from app.api import (
    alerts,
    calendar_auth,
    chores,
    icloud_auth,
    movies,
    photos,
    shopping,
    theme,
    weather,
    widgets,
)
from app.api import (
    assistant as assistant_api,
)
from app.api import (
    asus_router as asus_router_api,
)
from app.api import (
    devices as devices_api,
)
from app.api import (
    hdhomerun as hdhomerun_api,
)
from app.api import (
    jellyfin as jellyfin_api,
)
from app.api import (
    network_settings as network_settings_api,
)
from app.api import (
    packages as packages_api,
)
from app.api import (
    pihole as pihole_api,
)
from app.api import (
    qbittorrent as qbittorrent_api,
)
from app.api import (
    rss as rss_api,
)
from app.api import (
    screensaver as screensaver_api,
)
from app.api import (
    settings as settings_api,
)
from app.api import (
    setup as setup_api,
)
from app.api import (
    sports as sports_api,
)
from app.api import (
    tabs as tabs_api,
)
from app.api import (
    tts as tts_api,
)
from app.api import (
    users as users_api,
)
from app.api import (
    version as version_api,
)
from app.config import list_widget_configs, load_dashboard_config, settings
from app.logging_config import configure_logging, request_id_ctx
from app.plugins.base import registry
from app.plugins.network_settings import ensure_network_integration_defaults, resolve_network_settings
from app.plugins.registry_types import PLUGIN_CLASSES_BY_TYPE
from app.scheduler import (
    schedule_ai_widgets,
    schedule_package_refresh_widgets,
    schedule_photo_index_widgets,
    schedule_severe_weather_widgets,
    schedule_speedtest_widgets,
    scheduler,
)
from app.storage.db import get_widget_settings, init_db
from app.update_check import check_for_update, schedule_update_check

configure_logging()

logger = logging.getLogger(__name__)


def load_plugins() -> None:
    config = load_dashboard_config()
    for widget in list_widget_configs(config):
        if not widget.get("enabled", True):
            continue
        plugin_cls = PLUGIN_CLASSES_BY_TYPE.get(widget["type"])
        if plugin_cls is None:
            raise ValueError(f"No plugin registered for widget type '{widget['type']}'")
        # Settings changed at runtime (e.g. the weather widget's city) are
        # persisted separately from dashboard.yaml; layer them on top. The
        # plugin's own starter defaults sit underneath both, so a widget
        # that predates a plugin adding `default_settings` (or a UI-added
        # widget whose empty starter settings were never persisted) still
        # loads with usable settings instead of missing required keys.
        overrides = get_widget_settings(widget["id"]) or {}
        settings = {**plugin_cls.default_settings, **widget.get("settings", {}), **overrides}
        if plugin_cls.network_integration_type:
            settings = {**settings, **resolve_network_settings(plugin_cls, settings)}
        widget = {**widget, "settings": settings}
        registry.register(plugin_cls(widget))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_network_integration_defaults()
    load_plugins()
    schedule_ai_widgets()
    schedule_photo_index_widgets()
    schedule_speedtest_widgets()
    schedule_severe_weather_widgets()
    schedule_package_refresh_widgets()
    schedule_update_check(scheduler)
    scheduler.start()
    await check_for_update()
    yield
    scheduler.shutdown()


app = FastAPI(title="Tilora API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,  # required for the device/session cookies (app/auth.py)
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    # A fresh id per request, propagated via contextvars (see
    # app.logging_config.request_id_ctx) so every log line emitted anywhere
    # while handling this request — including from plugin/integration code
    # with no access to the request object — can be correlated, and echoed
    # back in a response header so client-side logs/bug reports can be
    # matched to a specific backend log line.
    request_id = uuid.uuid4().hex[:12]
    request_id_ctx.set(request_id)
    start = time.monotonic()
    response = await call_next(request)
    elapsed_ms = (time.monotonic() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info("%s %s -> %d (%.1fms)", request.method, request.url.path, response.status_code, elapsed_ms)
    return response


app.include_router(widgets.router)
app.include_router(tabs_api.router)
app.include_router(theme.router)
app.include_router(photos.router)
app.include_router(weather.router)
app.include_router(movies.router)
app.include_router(settings_api.router)
app.include_router(version_api.router)
app.include_router(alerts.router)
app.include_router(chores.router)
app.include_router(shopping.router)
app.include_router(packages_api.router)
app.include_router(calendar_auth.router)
app.include_router(icloud_auth.router)
app.include_router(assistant_api.router)
app.include_router(jellyfin_api.router)
app.include_router(hdhomerun_api.router)
app.include_router(pihole_api.router)
app.include_router(asus_router_api.router)
app.include_router(qbittorrent_api.router)
app.include_router(rss_api.router)
app.include_router(network_settings_api.router)
app.include_router(sports_api.router)
app.include_router(devices_api.router)
app.include_router(screensaver_api.router)
app.include_router(tts_api.router)
app.include_router(users_api.router)
app.include_router(setup_api.router)
app.include_router(admin_api.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
