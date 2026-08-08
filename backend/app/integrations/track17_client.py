"""17Track (17track.net) HTTP client for the packages plugin.

Auth is a single static API key sent as the `17token` header on every
request — no session/login step, unlike qbittorrent_client/pihole_client.
A tracking number has to be `register`ed with 17Track once before its
status can be polled via `get_track_info`; the plugin does both back to
back when a user adds a new tracking number (see `app.api.packages`).

17Track's v2.2 response envelope wraps every call's payload in
`{"code": ..., "data": {"accepted": [...], "rejected": [...]}}`, and each
per-number result nests carrier/status/event fields several levels deep.
Rather than assert on that exact shape, parsing here leans on `.get()`
throughout (mirroring `hdhomerun_client`'s defensive per-entry parsing) so
a field 17Track omits or a future API revision that adds/renames one
degrades to `None` instead of raising — a stale/partial status is far
less disruptive to a kiosk tile than a broken widget.
"""

from __future__ import annotations

from typing import Any

import httpx

_BASE_URL = "https://api.17track.net/track/v2.2"
_TIMEOUT_SECONDS = 15


class Track17Error(Exception):
    """Raised when the 17Track API can't be reached or rejects a request."""


def is_configured(settings: dict[str, Any]) -> bool:
    return bool(settings.get("track17_api_key"))


async def _post(api_key: str, path: str, payload: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{_BASE_URL}{path}",
                json=payload,
                headers={"17token": api_key, "Content-Type": "application/json"},
            )
    except httpx.HTTPError as exc:
        raise Track17Error(f"Could not reach 17Track: {exc}") from exc

    if response.status_code >= 400:
        raise Track17Error(f"17Track request failed (HTTP {response.status_code}).")

    try:
        body = response.json()
    except ValueError as exc:
        raise Track17Error("17Track returned a non-JSON response.") from exc

    code = body.get("code")
    if code not in (0, None):
        message = body.get("message") or f"error code {code}"
        raise Track17Error(f"17Track rejected the request: {message}")

    return body.get("data") or {}


async def register(api_key: str, tracking_number: str) -> None:
    """Register a tracking number with 17Track so it starts polling the carrier.

    17Track treats an already-registered number as a no-op success rather
    than an error, so this doesn't need to check for "already registered".
    """
    await _post(api_key, "/register", [{"number": tracking_number}])


def _carrier_of(entry: dict[str, Any]) -> str | None:
    carrier = entry.get("carrier")
    return None if carrier is None else str(carrier)


def _parse_track_info(entry: dict[str, Any]) -> dict[str, Any]:
    track_info = entry.get("track_info") or {}
    latest_status = track_info.get("latest_status") or {}
    latest_event = track_info.get("latest_event") or {}
    time_metrics = track_info.get("time_metrics") or {}
    estimated = time_metrics.get("estimated_delivery_date") or {}

    status = latest_status.get("status")
    return {
        "tracking_number": entry.get("number"),
        "carrier": _carrier_of(entry),
        "status": status,
        "last_event": latest_event.get("description") or latest_event.get("time_iso"),
        "eta_date": estimated.get("to") or estimated.get("from"),
        "delivered": bool(status) and status.lower() == "delivered",
    }


async def get_track_info(api_key: str, tracking_numbers: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch current status for a batch of tracking numbers.

    Returns a dict keyed by tracking number — entries 17Track rejected (bad
    number, not yet registered, etc) are simply absent rather than raising,
    so one bad number in a household's list doesn't fail the whole refresh.
    """
    if not tracking_numbers:
        return {}
    data = await _post(api_key, "/gettrackinfo", [{"number": number} for number in tracking_numbers])
    accepted = data.get("accepted") or []
    results: dict[str, dict[str, Any]] = {}
    for entry in accepted:
        number = entry.get("number")
        if number:
            results[number] = _parse_track_info(entry)
    return results
