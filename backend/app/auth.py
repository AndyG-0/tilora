"""Device/user identity: PIN hashing, session cookies, and the FastAPI
dependencies that resolve "who is asking" for each request.

Deliberately lightweight — this is a profile picker for a shared household
screen, not an internet-facing account system. See PIN handling below for
the threat model this is sized for.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException, Request, Response

from app.config import settings
from app.storage.db import get_device, get_session, get_user, touch_device

DEVICE_COOKIE_NAME = "tilora_device"
SESSION_COOKIE_NAME = "tilora_session"
DEVICE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365 * 5  # 5 years — a device is named once and rarely re-registered
SESSION_COOKIE_MAX_AGE = 60 * 60 * 24 * 90  # 90 days — long enough a kiosk screen doesn't re-prompt often
# last_seen_at only needs to be roughly current for the devices list in
# settings, so skip the write on requests within this interval of the last
# one instead of touching the device row on every single API call.
DEVICE_TOUCH_INTERVAL = timedelta(minutes=5)

# PBKDF2-HMAC-SHA256 with 210k iterations (OWASP's current baseline for that
# combination) protects a short PIN behind a self-hosted, LAN-scoped app —
# no argon2/bcrypt dependency is justified for this threat model, and this
# stays stdlib-only like the rest of the backend.
_PBKDF2_ITERATIONS = 210_000


def hash_pin(pin: str) -> tuple[str, str, int]:
    """Returns (hash_hex, salt_hex, iterations) for storage."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return digest.hex(), salt.hex(), _PBKDF2_ITERATIONS


def verify_pin(pin: str, pin_hash: str, pin_salt: str, iterations: int) -> bool:
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), bytes.fromhex(pin_salt), iterations)
    return hmac.compare_digest(digest.hex(), pin_hash)


def new_token() -> str:
    """A random, unguessable id used as both a row's primary key and its
    bearer credential (device ids and session ids double as cookie values).
    """
    return secrets.token_urlsafe(32)


def set_device_cookie(response: Response, device_id: str) -> None:
    response.set_cookie(
        DEVICE_COOKIE_NAME,
        device_id,
        max_age=DEVICE_COOKIE_MAX_AGE,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
    )


def set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_id,
        max_age=SESSION_COOKIE_MAX_AGE,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME)


async def get_current_device(request: Request) -> dict[str, Any]:
    """Resolves the device cookie to a device row.

    Never auto-provisions — only `POST /api/devices/register` creates a
    device row, so a stray GET can't silently mint one.
    """
    device_id = request.cookies.get(DEVICE_COOKIE_NAME)
    device = await asyncio.to_thread(get_device, device_id) if device_id else None
    if device is None:
        raise HTTPException(status_code=401, detail="No registered device")
    now = datetime.now(UTC)
    if now - datetime.fromisoformat(device["last_seen_at"]) >= DEVICE_TOUCH_INTERVAL:
        await asyncio.to_thread(touch_device, device["id"], now.isoformat())
    return device


async def get_current_session(request: Request) -> dict[str, Any]:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    session = await asyncio.to_thread(get_session, session_id) if session_id else None
    if session is None or session["expires_at"] < datetime.now(UTC).isoformat():
        raise HTTPException(status_code=401, detail="Not logged in")
    return session


async def get_current_user(session: dict[str, Any] = Depends(get_current_session)) -> dict[str, Any]:
    user = await asyncio.to_thread(get_user, session["user_id"])
    if user is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    return user


async def get_current_admin(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def session_expiry() -> str:
    return (datetime.now(UTC) + timedelta(seconds=SESSION_COOKIE_MAX_AGE)).isoformat()
