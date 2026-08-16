"""System-level operations (admin-only).

Currently provides a single endpoint to trigger an in-place software update
on native (systemd) installations.  Docker and manual setups are not
supported — the "Update now" button is hidden in the frontend when
TILORA_INSTALL_METHOD is not "native".
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.auth import get_current_admin
from app.update_check import INSTALL_METHOD, _update_state, run_update

router = APIRouter(prefix="/api/system", tags=["system"])


@router.post("/update")
async def trigger_update(
    background_tasks: BackgroundTasks,
    _: dict[str, Any] = Depends(get_current_admin),
) -> dict[str, str]:
    """Trigger an in-place software update (native installations only).

    Pulls the latest code on the configured branch, rebuilds both services,
    and restarts them via a sudoers-granted wrapper.  The restart kills this
    process; the frontend should poll ``GET /api/health`` until the backend
    comes back, then refresh the version info.

    Returns immediately with ``{"status": "update_started"}`` — the actual
    work runs in a FastAPI background task.
    """
    if INSTALL_METHOD != "native":
        raise HTTPException(
            status_code=400,
            detail="Software update is only supported for native (systemd) installations.",
        )
    if _update_state["running"]:
        raise HTTPException(
            status_code=409,
            detail="An update is already in progress.",
        )
    background_tasks.add_task(run_update)
    return {"status": "update_started"}
