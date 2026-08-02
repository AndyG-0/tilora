"""Docker plugin: container list and health/state for a single Docker host,
via the Docker Engine API (see `app/integrations/docker_client.py` for the
socket-vs-TCP connection handling).

The default settings point at the standard local socket path
(`/var/run/docker.sock`), so a backend that has that socket available (e.g.
bind-mounted into its own container, or running directly on the Docker host)
works out of the box with no configuration. Switching `connection` to "tcp"
targets a separate host's Docker API instead, unauthenticated over the LAN —
same trusted-network assumption Pi-hole/HDHomeRun make. Either way,
get_summary/get_detail return a not-connected or an error state rather than
raising, so the widget degrades gracefully when the daemon isn't reachable.
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.integrations import docker_client
from app.plugins.base import Plugin, ToolDef


class DockerPlugin(Plugin):
    id = "docker"
    name = "Docker"
    refresh_interval_seconds = 30
    default_settings: ClassVar[dict[str, Any]] = {
        "connection": "socket",  # "socket" | "tcp"
        "socket_path": "/var/run/docker.sock",
        "host": "",
        "port": 2375,
    }
    default_layout: ClassVar[dict[str, int]] = {"colSpan": 2, "rowSpan": 1}

    def _settings(self) -> dict[str, Any]:
        return self.config["settings"]

    def _is_connected(self) -> bool:
        return docker_client.is_configured(self._settings())

    def _settings_view(self) -> dict[str, Any]:
        s = self._settings()
        return {
            "connection": s.get("connection", "socket"),
            "socket_path": s.get("socket_path", "/var/run/docker.sock"),
            "host": s.get("host", ""),
            "port": s.get("port", 2375),
        }

    async def _containers(self) -> tuple[list[dict[str, Any]], str | None]:
        if not self._is_connected():
            return [], None
        try:
            containers = await docker_client.fetch_containers(self._settings())
        except docker_client.DockerError as exc:
            return [], str(exc)
        return containers, None

    async def get_summary(self) -> dict[str, Any]:
        connected = self._is_connected()
        containers, error = await self._containers()
        running = sum(1 for c in containers if c["state"] == "running")
        result: dict[str, Any] = {
            "connected": connected,
            "containers": [{"name": c["name"], "state": c["state"], "status": c["status"]} for c in containers],
            "running_count": running,
            "stopped_count": len(containers) - running,
            "total_count": len(containers),
            **self._settings_view(),
        }
        if error:
            result["error"] = error
        return result

    @staticmethod
    def _empty_detail_fields() -> dict[str, Any]:
        return {"containers": []}

    async def get_detail(self) -> dict[str, Any]:
        summary = await self.get_summary()
        if not summary["connected"] or summary.get("error"):
            return {**summary, **self._empty_detail_fields()}

        containers, error = await self._containers()
        if error:
            return {**summary, "error": error, **self._empty_detail_fields()}

        return {
            **summary,
            "containers": [
                {
                    "id": c["id"],
                    "name": c["name"],
                    "image": c["image"],
                    "state": c["state"],
                    "status": c["status"],
                }
                for c in containers
            ],
        }

    def get_ai_tools(self) -> list[ToolDef]:
        async def get_docker_container_status() -> dict[str, Any]:
            return await self.get_summary()

        return [
            ToolDef(
                name="get_docker_container_status",
                description="Get the list of Docker containers on the configured host, their "
                "running/stopped state, and counts of running vs. stopped containers.",
                parameters={"type": "object", "properties": {}},
                handler=get_docker_container_status,
            )
        ]
