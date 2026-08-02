from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    alerts,
    calendar_auth,
    icloud_auth,
    photos,
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
    pihole as pihole_api,
)
from app.api import (
    settings as settings_api,
)
from app.api import (
    sports as sports_api,
)
from app.api import (
    synology as synology_api,
)
from app.api import (
    tabs as tabs_api,
)
from app.api import (
    users as users_api,
)
from app.api import (
    version as version_api,
)
from app.config import list_widget_configs, load_dashboard_config, settings
from app.plugins.base import registry
from app.plugins.registry_types import PLUGIN_CLASSES_BY_TYPE
from app.scheduler import schedule_ai_widgets, schedule_photo_index_widgets, scheduler
from app.storage.db import get_widget_settings, init_db
from app.update_check import check_for_update, schedule_update_check


def load_plugins() -> None:
    config = load_dashboard_config()
    for widget in list_widget_configs(config):
        if not widget.get("enabled", True):
            continue
        plugin_cls = PLUGIN_CLASSES_BY_TYPE.get(widget["type"])
        if plugin_cls is None:
            raise ValueError(f"No plugin registered for widget type '{widget['type']}'")
        # Settings changed at runtime (e.g. the weather widget's city) are
        # persisted separately from dashboard.yaml; layer them on top.
        overrides = get_widget_settings(widget["id"])
        if overrides:
            widget = {**widget, "settings": {**widget.get("settings", {}), **overrides}}
        registry.register(plugin_cls(widget))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    load_plugins()
    schedule_ai_widgets()
    schedule_photo_index_widgets()
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

app.include_router(widgets.router)
app.include_router(tabs_api.router)
app.include_router(theme.router)
app.include_router(photos.router)
app.include_router(weather.router)
app.include_router(settings_api.router)
app.include_router(version_api.router)
app.include_router(alerts.router)
app.include_router(calendar_auth.router)
app.include_router(icloud_auth.router)
app.include_router(assistant_api.router)
app.include_router(jellyfin_api.router)
app.include_router(hdhomerun_api.router)
app.include_router(pihole_api.router)
app.include_router(synology_api.router)
app.include_router(asus_router_api.router)
app.include_router(sports_api.router)
app.include_router(devices_api.router)
app.include_router(users_api.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
