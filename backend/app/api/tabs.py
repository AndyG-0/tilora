from __future__ import annotations

from fastapi import APIRouter

from app.config import load_dashboard_config, resolve_tabs

router = APIRouter(prefix="/api/tabs", tags=["tabs"])


@router.get("")
async def list_tabs():
    return resolve_tabs(load_dashboard_config())
