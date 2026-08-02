"""Podman REST API client for the Podman plugin.

Podman's REST API (`podman system service`) is Docker-Engine-API-compatible
— the same `/containers/json?all=true` endpoint, same field shapes — so this
is a near-verbatim copy of `docker_client.py` with Podman's own connection
defaults:

- "socket" (default): Podman's local unix socket. Rootful Podman listens on
  `/run/podman/podman.sock`; rootless Podman listens on
  `$XDG_RUNTIME_DIR/podman/podman.sock` (commonly
  `/run/user/<uid>/podman/podman.sock`) — there's no single universal
  default the way Docker has one, so the plugin's default is the rootful
  path and rootless users are expected to override `socket_path`.
- "tcp": `podman system service tcp:0.0.0.0:8080` exposed in plain,
  unauthenticated HTTP — same trusted-home-LAN threat model as the Docker
  and Pi-hole/HDHomeRun integrations.
"""

from __future__ import annotations

from typing import Any

import httpx

_DEFAULT_SOCKET_PATH = "/run/podman/podman.sock"
_DEFAULT_TCP_PORT = 8080


class PodmanError(Exception):
    """Raised when the Podman API can't be reached or rejects a request."""


def is_configured(settings: dict[str, Any]) -> bool:
    if settings.get("connection", "socket") == "tcp":
        return bool(settings.get("host"))
    return bool(settings.get("socket_path", _DEFAULT_SOCKET_PATH))


def _client(settings: dict[str, Any]) -> httpx.AsyncClient:
    if settings.get("connection", "socket") == "tcp":
        host = settings.get("host", "")
        port = settings.get("port", _DEFAULT_TCP_PORT)
        return httpx.AsyncClient(base_url=f"http://{host}:{port}", timeout=10)
    socket_path = settings.get("socket_path") or _DEFAULT_SOCKET_PATH
    transport = httpx.AsyncHTTPTransport(uds=socket_path)
    # The host in this base URL is never actually resolved (the uds transport
    # connects straight to the socket file), it just needs to be a valid URL.
    return httpx.AsyncClient(transport=transport, base_url="http://podman", timeout=10)


def _container_dict(entry: dict[str, Any]) -> dict[str, Any]:
    names = entry.get("Names") or []
    container_id = entry.get("Id", "")
    return {
        "id": container_id[:12],
        "name": names[0].lstrip("/") if names else container_id[:12],
        "image": entry.get("Image", ""),
        "state": entry.get("State", ""),
        "status": entry.get("Status", ""),
    }


async def fetch_containers(settings: dict[str, Any]) -> list[dict[str, Any]]:
    async with _client(settings) as client:
        try:
            response = await client.get("/containers/json", params={"all": "true"})
        except httpx.HTTPError as exc:
            raise PodmanError(f"Could not reach the Podman API: {exc}") from exc

    if response.status_code >= 400:
        raise PodmanError(f"Podman API request failed (HTTP {response.status_code}).")

    try:
        data = response.json()
    except ValueError as exc:
        raise PodmanError(f"Unexpected (non-JSON) response from the Podman API: {exc}") from exc
    if not isinstance(data, list):
        raise PodmanError("Unexpected response shape from the Podman API.")

    return [_container_dict(entry) for entry in data]
