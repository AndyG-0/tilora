"""Asus router (AsusWRT/Merlin firmware) HTTP client for the Asus Router
plugin.

Auth is token-based, same cache-until-rejected shape as `synology_client`:
`POST /login.cgi` with a base64 `user:pass` `login_authorization` field
returns an `asus_token`, cached in-memory (see `storage/cache.py`) and sent
as a cookie on every subsequent request until one comes back
unauthorized, at which point one re-auth-and-retry happens.

Data comes from the router's `appGet.cgi` "hook" endpoint, the same
JSON-RPC-ish interface the stock web UI uses internally. The exact hook
names/response shapes below (`get_clientlist`, `wanlink`, `netdev`) are
long-standing conventions across AsusWRT/Merlin firmware versions but are
not formally documented by Asus, so treat unexpected response shapes from a
real router as a firmware-version quirk to account for rather than a bug
here.
"""

from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.storage.cache import cache

_LOGGER = logging.getLogger(__name__)

_SESSION_TTL_SECONDS = 1800

_USER_AGENT = "Mozilla/5.0 (compatible; Tilora)"

# Field names/values captured from a real browser's login POST to a Merlin
# router's Main_Login.asp form (verified via a live DevTools trace against
# the user's own router). action_mode and next_page must be sent EMPTY, not
# populated with plausible-looking values ("apply"/"index.asp") — the
# firmware rejects the login (re-serving the login page instead of
# validating credentials) when they're anything else, and login_captcha,
# while always empty on this firmware, must still be present as a field.
_LOGIN_FORM_FIELDS = {
    "group_id": "",
    "action_mode": "",
    "action_script": "",
    "action_wait": "5",
    "current_page": "Main_Login.asp",
    "next_page": "",
    "login_captcha": "",
}


# Some hooks (observed on `wanlink()`) don't return JSON at all — they
# return a blob of JS meant to be eval()'d, defining a bunch of top-level
# `function name() { return <value>; }` declarations that the stock web UI
# calls individually to read each field. Extract those name/value pairs
# directly instead of trying to parse the surrounding (non-JSON, often
# malformed-looking) wrapper.
_HOOK_JS_FUNCTION_PATTERN = re.compile(
    r"function\s+([A-Za-z0-9_]+)\s*\(\s*\)\s*\{\s*return\s+(.*?)\s*;\s*\}", re.DOTALL
)


def _parse_js_literal(raw: str) -> Any:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return raw[1:-1]
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def _parse_js_hook_functions(text: str) -> dict[str, Any] | None:
    matches = _HOOK_JS_FUNCTION_PATTERN.findall(text)
    if not matches:
        return None
    return {name: _parse_js_literal(value) for name, value in matches}


# `netdev(appobj)` returns yet another non-JSON shape: a JS object literal
# with single-quoted keys and bare (often hex, e.g. `0xc1ea8ae3a` — plain
# decimal can't hold some of these 64-bit byte counters as a JS float
# without losing precision) numeric values, nested inside a malformed
# `{"netdev":{netdev = {...}}}` wrapper. Pull the per-interface rx/tx pairs
# out directly rather than trying to fix up the wrapper into valid JSON.
_HOOK_NETDEV_ENTRY_PATTERN = re.compile(
    r"'([A-Za-z0-9_]+)'\s*:\s*\{\s*rx\s*:\s*(0[xX][0-9a-fA-F]+|\d+)\s*,\s*tx\s*:\s*(0[xX][0-9a-fA-F]+|\d+)\s*\}"
)


def _parse_int_literal(raw: str) -> int:
    return int(raw, 16) if raw.lower().startswith("0x") else int(raw)


def _parse_js_netdev_response(text: str) -> dict[str, Any] | None:
    matches = _HOOK_NETDEV_ENTRY_PATTERN.findall(text)
    if not matches:
        return None
    netdev: dict[str, int] = {}
    for iface, rx, tx in matches:
        netdev[f"{iface}_rx"] = _parse_int_literal(rx)
        netdev[f"{iface}_tx"] = _parse_int_literal(tx)
    return {"netdev": netdev}


def _html_snippet(html: str) -> str:
    """Best-effort short description of an HTML page, for error messages.

    Prefers the <title>; falls back to the first chunk of visible text.
    Not meant to be exhaustive — just enough to tell "login form" apart from
    "captcha challenge" apart from "device is rebooting" in a bug report.
    """
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    text = match.group(1) if match else html
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:80] or "untitled page"


class AsusRouterError(Exception):
    """Raised when an Asus router can't be reached or rejects a request."""


@dataclass
class AsusRouterSession:
    token: str


def is_configured(settings: dict[str, Any]) -> bool:
    return bool(settings.get("host")) and bool(settings.get("username")) and bool(settings.get("password"))


def _base_url(settings: dict[str, Any]) -> str:
    scheme = "https" if settings.get("use_https", True) else "http"
    default_port = 443 if scheme == "https" else 80
    port = settings.get("port", default_port)
    host = settings["host"]
    # Omit the port when it's the scheme's default, matching what a real
    # browser sends as Origin/Referer/Host (e.g. "http://192.168.50.1", not
    # "http://192.168.50.1:80"). Some router firmware does a literal
    # string/prefix check of Origin/Referer against the LAN IP as a CSRF
    # guard, and a stray ":80"/":443" suffix fails that check — the request
    # then gets silently bounced back to the login page instead of being
    # validated, indistinguishable from a rejected password.
    if port == default_port:
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"


async def _authenticate(base_url: str, widget_id: str, username: str, password: str) -> AsusRouterSession:
    credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    request_headers = {
        "User-Agent": _USER_AGENT,
        "Referer": f"{base_url}/Main_Login.asp",
        "Origin": base_url,
    }
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        try:
            response = await client.post(
                f"{base_url}/login.cgi",
                data={**_LOGIN_FORM_FIELDS, "login_authorization": credentials},
                headers=request_headers,
            )
        except httpx.HTTPError as exc:
            raise AsusRouterError(f"Could not reach the router: {exc}") from exc

        # Read from the client's accumulated cookie jar, not just the final
        # response's own cookies — if the firmware sets asus_token on a 302
        # and then redirects to a page that doesn't repeat the header,
        # `response.cookies` alone would miss it once follow_redirects hops
        # past that first response.
        token = client.cookies.get("asus_token") or response.cookies.get("asus_token")

    if response.status_code >= 400:
        raise AsusRouterError(f"Router login failed (HTTP {response.status_code}).")

    body: dict[str, Any] | None = None
    if not token:
        try:
            body = response.json()
            token = body.get("asus_token")
        except ValueError:
            body = None
    if not token:
        if body is not None and body.get("error_status"):
            # Merlin firmware's login-attempt-limit/lockout signal — a
            # distinct failure from a plain wrong password.
            raise AsusRouterError(
                f"Router rejected the login attempt (error_status {body['error_status']}) — it may be "
                "temporarily locked out after repeated failed attempts."
            )
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            snippet = _html_snippet(response.text)
            # Logged at warning level (not the credentials) so the exact
            # request this process actually sent is available in the
            # console the next time this happens, instead of requiring
            # another manual browser-vs-backend comparison.
            _LOGGER.warning(
                "ASUS login POST %s/login.cgi rejected: sent headers=%s form-keys=%s -> status=%s "
                "content-type=%s body[:200]=%r",
                base_url,
                request_headers,
                sorted(_LOGIN_FORM_FIELDS),
                response.status_code,
                content_type,
                response.text[:200],
            )
            raise AsusRouterError(
                f'Router returned its login page instead of a token (page: "{snippet}") — double check the '
                "host/port/use_https settings match how the router is actually reached. If those are "
                "correct, this firmware may require a login flow (e.g. a CSRF token from the login page, "
                "or a captcha) that isn't supported yet."
            )
        raise AsusRouterError("Router rejected that username/password.")

    session = AsusRouterSession(token=token)
    cache.set(f"asus_token:{widget_id}", session, _SESSION_TTL_SECONDS)
    return session


async def _resolve_session(
    settings: dict[str, Any], widget_id: str, *, force_reauth: bool = False
) -> AsusRouterSession:
    cache_key = f"asus_token:{widget_id}"
    session = None if force_reauth else cache.get(cache_key)
    if session is None:
        base_url = _base_url(settings)
        session = await _authenticate(
            base_url, widget_id, settings.get("username") or "", settings.get("password") or ""
        )
    return session


async def _hook(hook_call: str, *, settings: dict[str, Any], widget_id: str) -> Any:
    base_url = _base_url(settings)
    session = await _resolve_session(settings, widget_id)

    async def send(session: AsusRouterSession) -> httpx.Response:
        cookies = httpx.Cookies()
        cookies.set("asus_token", session.token)
        async with httpx.AsyncClient(timeout=10, cookies=cookies, follow_redirects=True) as client:
            return await client.post(
                f"{base_url}/appGet.cgi",
                data={"hook": hook_call},
                headers={"User-Agent": _USER_AGENT, "Referer": f"{base_url}/index.asp"},
            )

    try:
        response = await send(session)
    except httpx.HTTPError as exc:
        raise AsusRouterError(f"Could not reach the router: {exc}") from exc

    if response.status_code in (401, 403):
        session = await _resolve_session(settings, widget_id, force_reauth=True)
        try:
            response = await send(session)
        except httpx.HTTPError as exc:
            raise AsusRouterError(f"Could not reach the router: {exc}") from exc

    if response.status_code >= 400:
        raise AsusRouterError(f"Router request failed (HTTP {response.status_code}).")

    try:
        return response.json()
    except ValueError as exc:
        parsed = _parse_js_hook_functions(response.text) or _parse_js_netdev_response(response.text)
        if parsed is not None:
            return parsed
        # Logged at warning level so the actual (unparseable) body the
        # router sent back is visible in the console next time, instead of
        # guessing at the exact shape blind.
        _LOGGER.warning(
            "ASUS hook POST %s/appGet.cgi hook=%r -> status=%s content-type=%s body[:300]=%r",
            base_url,
            hook_call,
            response.status_code,
            response.headers.get("content-type"),
            response.text[:300],
        )
        raise AsusRouterError("Router returned an unexpected response.") from exc


async def test_connection(settings: dict[str, Any], widget_id: str) -> str:
    data = await _hook("nvram_get(productid)", settings=settings, widget_id=widget_id)
    return data.get("productid") or "Asus Router"


async def get_clients(settings: dict[str, Any], widget_id: str) -> list[dict[str, Any]]:
    data = await _hook("get_clientlist(appobj)", settings=settings, widget_id=widget_id)
    entries = (data.get("get_clientlist") or {}) if isinstance(data, dict) else {}
    clients = []
    for mac, info in entries.items():
        if mac == "maclist" or not isinstance(info, dict):
            continue
        clients.append(
            {
                "name": info.get("nickName") or info.get("name") or mac,
                "ip": info.get("ip") or "",
                "online": bool(int(info.get("isOnline", 0)))
                if str(info.get("isOnline", "0")).isdigit()
                else bool(info.get("isOnline")),
            }
        )
    return clients


async def get_wan_status(settings: dict[str, Any], widget_id: str) -> dict[str, Any]:
    data = await _hook("wanlink()", settings=settings, widget_id=widget_id)
    # `wanlink_status`'s numeric convention isn't consistent across
    # firmware/hardware (observed a real router report status 1 while its
    # own `wanlink_statusstr` said "Connected") — the status string is the
    # one field the firmware itself treats as authoritative for display, so
    # trust that instead of a hardcoded magic number.
    connected = str(data.get("wanlink_statusstr") or "").strip().lower() == "connected"
    return {
        "connected": connected,
        "ip": data.get("wanlink_ipaddr") or None,
    }


async def get_traffic(settings: dict[str, Any], widget_id: str) -> dict[str, Any]:
    data = await _hook("netdev(appobj)", settings=settings, widget_id=widget_id)
    netdev = (data.get("netdev") or {}) if isinstance(data, dict) else {}
    return {
        "rx_bytes": int(netdev.get("INTERNET_rx", 0) or 0),
        "tx_bytes": int(netdev.get("INTERNET_tx", 0) or 0),
    }
