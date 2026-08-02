from __future__ import annotations

from fastapi import APIRouter

from app.update_check import get_update_status

router = APIRouter(prefix="/api/version", tags=["version"])


@router.get("")
async def get_version():
    return get_update_status()
