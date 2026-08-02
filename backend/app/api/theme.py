from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/theme", tags=["theme"])

# v1 ships two themes; the frontend owns the actual CSS. This endpoint just
# tells the UI what's selectable and what to default to.
_THEMES = [
    {"id": "light", "name": "Light"},
    {"id": "dark", "name": "Dark"},
    {"id": "sepia", "name": "Sepia"},
    {"id": "contrast", "name": "High Contrast"},
]


@router.get("")
async def get_theme():
    return {"themes": _THEMES, "default": "dark"}
