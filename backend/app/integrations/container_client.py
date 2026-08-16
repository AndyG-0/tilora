"""Container Engine API client for the Container plugin (Docker or Podman).

Docker and Podman both speak the same REST API shape (Podman's `podman
system service` is Docker-Engine-API-compatible) — same `/containers/json?
all=true` endpoint, same field shapes — so one client talks to either engine
over HTTP via httpx, the same thin-client-per-integration approach used
everywhere else in this codebase (no `docker`/`podman` Python SDK
dependency). Which engine's daemon is actually on the other end is entirely
a function of the connection settings passed in (socket path / host / port)
— nothing here needs to know or care which engine it's talking to. Two
connection modes are supported, matching the two ways a home-lab container
host is typically reachable:

- "socket" (default): a local unix socket, e.g. `/var/run/docker.sock`
  (Docker) or `/run/podman/podman.sock` (Podman, rootful — rootless Podman
  listens on `$XDG_RUNTIME_DIR/podman/podman.sock` instead) — reachable when
  this backend runs on (or has that socket bind-mounted into) the same host
  as the daemon. httpx talks to it via `httpx.AsyncHTTPTransport(uds=...)`.
- "tcp": a remote host's API exposed in plain, unauthenticated HTTP (e.g.
  `dockerd -H tcp://0.0.0.0:2375` or `podman system service
  tcp:0.0.0.0:8080`) — the same trusted-home-LAN threat model already
  assumed by the Pi-hole/HDHomeRun integrations, so no TLS/auth support is
  needed for this.

Only `/containers/json?all=true` is used — it already includes per-container
state/status/image/name, so there's no need for an N+1 `/containers/{id}/json`
call per container.
"""

from __future__ import annotations

from typing import Any

import httpx

_DEFAULT_SOCKET_PATH = "/var/run/docker.sock"
_DEFAULT_TCP_PORT = 2375


class ContainerError(Exception):
    """Raised when a container engine's API can't be reached or rejects a request."""


def is_configured(settings: dict[str, Any]) -> bool:
    if settings.get("connection", "socket") == "tcp":
        return bool(settings.get("host"))
    return bool(settings.get("socket_path", _DEFAULT_SOCKET_PATH))


# Different Container widgets can point at different hosts/sockets, so a
# single global client won't do — pool one client per distinct connection
# target instead, keyed off the settings that determine that target, and
# reuse it across polls (this plugin's default refresh_interval_seconds is
# 30s) rather than paying a fresh connection per request.
_clients: dict[str, httpx.AsyncClient] = {}


def _client_key(settings: dict[str, Any]) -> str:
    if settings.get("connection", "socket") == "tcp":
        host = settings.get("host", "")
        port = settings.get("port", _DEFAULT_TCP_PORT)
        return f"tcp:{host}:{port}"
    socket_path = settings.get("socket_path") or _DEFAULT_SOCKET_PATH
    return f"socket:{socket_path}"


def _client(settings: dict[str, Any]) -> httpx.AsyncClient:
    key = _client_key(settings)
    client = _clients.get(key)
    if client is not None:
        return client

    if settings.get("connection", "socket") == "tcp":
        host = settings.get("host", "")
        port = settings.get("port", _DEFAULT_TCP_PORT)
        client = httpx.AsyncClient(base_url=f"http://{host}:{port}", timeout=10)
    else:
        socket_path = settings.get("socket_path") or _DEFAULT_SOCKET_PATH
        transport = httpx.AsyncHTTPTransport(uds=socket_path)
        # The host in this base URL is never actually resolved (the uds
        # transport connects straight to the socket file), it just needs to
        # be a valid URL.
        client = httpx.AsyncClient(transport=transport, base_url="http://container", timeout=10)

    _clients[key] = client
    return client


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


async def test_connection(settings: dict[str, Any]) -> str:
    containers = await fetch_containers(settings)
    return f"Connected ({len(containers)} container{'s' if len(containers) != 1 else ''} found)"


async def fetch_containers(settings: dict[str, Any]) -> list[dict[str, Any]]:
    client = _client(settings)
    try:
        response = await client.get("/containers/json", params={"all": "true"})
    except httpx.HTTPError as exc:
        raise ContainerError(f"Could not reach the container API: {exc}") from exc

    if response.status_code >= 400:
        raise ContainerError(f"Container API request failed (HTTP {response.status_code}).")

    try:
        data = response.json()
    except ValueError as exc:
        raise ContainerError(f"Unexpected (non-JSON) response from the container API: {exc}") from exc
    if not isinstance(data, list):
        raise ContainerError("Unexpected response shape from the container API.")

    return [_container_dict(entry) for entry in data]
