"""Docker Engine API client for the Docker plugin.

Talks to the Docker Engine API directly over HTTP via httpx, the same
thin-client-per-integration approach used everywhere else in this codebase —
no `docker` Python SDK dependency. Two connection modes are supported,
matching the two ways a home-lab Docker host is typically reachable:

- "socket" (default): a local unix socket, normally `/var/run/docker.sock` —
  reachable when this backend runs on (or has that socket bind-mounted into)
  the same host as the Docker daemon. httpx talks to it via
  `httpx.AsyncHTTPTransport(uds=...)`.
- "tcp": a remote host's Docker API exposed in plain, unauthenticated HTTP
  (`dockerd -H tcp://0.0.0.0:2375`) — the same trusted-home-LAN threat model
  already assumed by the Pi-hole/HDHomeRun integrations, so no TLS/auth
  support is needed for this.

Only `/containers/json?all=true` is used — it already includes per-container
state/status/image/name, so there's no need for an N+1 `/containers/{id}/json`
call per container.
"""

from __future__ import annotations

from typing import Any

import httpx

_DEFAULT_SOCKET_PATH = "/var/run/docker.sock"
_DEFAULT_TCP_PORT = 2375


class DockerError(Exception):
    """Raised when a Docker Engine API can't be reached or rejects a request."""


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
    return httpx.AsyncClient(transport=transport, base_url="http://docker", timeout=10)


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
            raise DockerError(f"Could not reach the Docker API: {exc}") from exc

    if response.status_code >= 400:
        raise DockerError(f"Docker API request failed (HTTP {response.status_code}).")

    try:
        data = response.json()
    except ValueError as exc:
        raise DockerError(f"Unexpected (non-JSON) response from the Docker API: {exc}") from exc
    if not isinstance(data, list):
        raise DockerError("Unexpected response shape from the Docker API.")

    return [_container_dict(entry) for entry in data]
