from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.auth import (
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    get_current_device,
    get_current_user,
    hash_pin,
    new_token,
    session_expiry,
    set_session_cookie,
    verify_pin,
)
from app.storage.db import (
    create_session,
    create_user,
    delete_expired_sessions,
    delete_session,
    delete_user,
    get_user,
    get_user_preferences,
    list_users,
    save_user_preferences,
    update_user,
)

router = APIRouter(prefix="/api/users", tags=["users"])

_PIN_PATTERN = r"^\d{4,8}$"


class CreateUserRequest(BaseModel):
    name: str
    avatar: str | None = None
    pin: str | None = Field(default=None, pattern=_PIN_PATTERN)


class LoginRequest(BaseModel):
    pin: str | None = None


class UpdateUserRequest(BaseModel):
    name: str | None = None
    avatar: str | None = None
    # "" clears an existing PIN (same convention as settings.py's secret
    # clearing); anything else must look like a PIN.
    pin: str | None = Field(default=None, pattern=r"^$|^\d{4,8}$")


class UpdatePreferencesRequest(BaseModel):
    theme: str | None = None


def _profile_shape(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "name": user["name"],
        "avatar": user["avatar"],
        "has_pin": bool(user["pin_hash"]),
    }


def _me_shape(user: dict[str, Any]) -> dict[str, Any]:
    return {"id": user["id"], "name": user["name"], "avatar": user["avatar"]}


@router.get("")
async def list_profiles():
    users = await asyncio.to_thread(list_users)
    return [_profile_shape(u) for u in users]


@router.post("")
async def create_profile(
    payload: CreateUserRequest, response: Response, device: dict[str, Any] = Depends(get_current_device)
):
    pin_hash = pin_salt = None
    pin_iterations = None
    if payload.pin:
        pin_hash, pin_salt, pin_iterations = hash_pin(payload.pin)

    user_id = uuid4().hex
    now = datetime.now(UTC).isoformat()
    await asyncio.to_thread(
        create_user, user_id, payload.name, payload.avatar, pin_hash, pin_salt, pin_iterations, now
    )

    session_id = new_token()
    await asyncio.to_thread(create_session, session_id, user_id, device["id"], now, session_expiry())
    set_session_cookie(response, session_id)

    return _me_shape({"id": user_id, "name": payload.name, "avatar": payload.avatar})


@router.post("/{user_id}/login")
async def login(
    user_id: str, payload: LoginRequest, response: Response, device: dict[str, Any] = Depends(get_current_device)
):
    user = await asyncio.to_thread(get_user, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"Unknown profile '{user_id}'")

    if user["pin_hash"]:
        if not payload.pin or not verify_pin(payload.pin, user["pin_hash"], user["pin_salt"], user["pin_iterations"]):
            raise HTTPException(status_code=401, detail="Incorrect PIN")

    session_id = new_token()
    now = datetime.now(UTC).isoformat()
    # Login (profile switch) is the natural, frequent moment to reap sessions
    # that expired since they were created — nothing else ever purges them.
    await asyncio.to_thread(delete_expired_sessions, now)
    await asyncio.to_thread(create_session, session_id, user["id"], device["id"], now, session_expiry())
    set_session_cookie(response, session_id)

    return _me_shape(user)


@router.post("/logout")
async def logout(request: Request, response: Response):
    # Reads the cookie directly (rather than depending on get_current_user)
    # so logging out an already-expired/invalid session still clears the
    # cookie instead of 401ing.
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        await asyncio.to_thread(delete_session, session_id)
    clear_session_cookie(response)
    return {"status": "ok"}


@router.get("/me")
async def current_profile(user: dict[str, Any] = Depends(get_current_user)):
    return _me_shape(user)


@router.patch("/me")
async def update_profile(payload: UpdateUserRequest, user: dict[str, Any] = Depends(get_current_user)):
    fields = payload.model_dump(exclude_unset=True, exclude={"pin"})
    if "pin" in payload.model_fields_set:
        if payload.pin == "":
            fields.update(pin_hash=None, pin_salt=None, pin_iterations=None)
        elif payload.pin is not None:
            pin_hash, pin_salt, pin_iterations = hash_pin(payload.pin)
            fields.update(pin_hash=pin_hash, pin_salt=pin_salt, pin_iterations=pin_iterations)
    if fields:
        await asyncio.to_thread(update_user, user["id"], **fields)
    updated = await asyncio.to_thread(get_user, user["id"])
    return _me_shape(updated)


@router.delete("/me")
async def delete_profile(user: dict[str, Any] = Depends(get_current_user)):
    all_users = await asyncio.to_thread(list_users)
    if len(all_users) <= 1:
        raise HTTPException(status_code=400, detail="Can't delete the only remaining profile")
    await asyncio.to_thread(delete_user, user["id"])
    return {"status": "ok"}


@router.get("/me/preferences")
async def get_preferences(user: dict[str, Any] = Depends(get_current_user)):
    return await asyncio.to_thread(get_user_preferences, user["id"])


@router.patch("/me/preferences")
async def update_preferences(payload: UpdatePreferencesRequest, user: dict[str, Any] = Depends(get_current_user)):
    overrides = payload.model_dump(exclude_unset=True)
    return await asyncio.to_thread(save_user_preferences, user["id"], overrides)
