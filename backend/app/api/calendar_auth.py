from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from app.auth import get_current_admin
from app.config import effective_settings, settings
from app.integrations import caldav_client, google_oauth, microsoft_oauth
from app.storage.cache import cache

router = APIRouter(prefix="/api/calendar", tags=["calendar"], dependencies=[Depends(get_current_admin)])


_OAUTH_STATE_TTL_SECONDS = 600


@router.get("/auth/start")
async def start_auth():
    creds = effective_settings()
    if not creds["google_calendar_client_id"]:
        raise HTTPException(status_code=400, detail="Google Calendar client id is not configured")
    url, state = google_oauth.build_auth_url()
    cache.set(f"oauth_state:google:{state}", True, _OAUTH_STATE_TTL_SECONDS)
    return RedirectResponse(url)


@router.get("/auth/callback")
async def auth_callback(code: str, state: str):
    if cache.get(f"oauth_state:google:{state}") is None:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    cache.delete(f"oauth_state:google:{state}")
    await google_oauth.exchange_code(code)
    cache.delete_prefix("summary:calendar:")
    cache.delete_prefix("detail:calendar:")
    return RedirectResponse(f"{settings.cors_origin}/settings")


@router.get("/auth/microsoft/start")
async def start_microsoft_auth():
    creds = effective_settings()
    if not creds["microsoft_calendar_client_id"]:
        raise HTTPException(status_code=400, detail="Microsoft Calendar client id is not configured")
    url, state = microsoft_oauth.build_auth_url()
    cache.set(f"oauth_state:microsoft:{state}", True, _OAUTH_STATE_TTL_SECONDS)
    return RedirectResponse(url)


@router.get("/auth/microsoft/callback")
async def microsoft_auth_callback(code: str, state: str):
    if cache.get(f"oauth_state:microsoft:{state}") is None:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    cache.delete(f"oauth_state:microsoft:{state}")
    await microsoft_oauth.exchange_code(code)
    # "calendar" is the dashboard.yaml-defined widget id (used when that
    # widget's own `provider` setting is switched to "microsoft");
    # "calendar_microsoft" is this provider's own dashboard-widget id
    # convention (the type a UI-added "Outlook Calendar" widget starts
    # from) — clear both so either configuration picks up the fresh
    # connection immediately rather than waiting out the cache TTL.
    cache.delete_prefix("summary:calendar:")
    cache.delete_prefix("detail:calendar:")
    cache.delete_prefix("summary:calendar_microsoft:")
    cache.delete_prefix("detail:calendar_microsoft:")
    return RedirectResponse(f"{settings.cors_origin}/settings")


@router.get("/status")
async def calendar_status():
    return {"connected": google_oauth.is_connected()}


@router.get("/caldav/calendars")
async def list_caldav_calendars():
    creds = effective_settings()
    if not caldav_client.is_configured(creds):
        raise HTTPException(status_code=400, detail="CalDAV is not configured")
    return await caldav_client.list_calendars(creds["caldav_url"], creds["caldav_username"], creds["caldav_password"])
