"""Container plugin: container list and health/state for a single Docker or
Podman host, via `app/integrations/container_client.py` (both engines share
the same Docker-Engine-API-compatible REST shape).

Which engine a widget instance talks to is just its `engine` setting
("docker" | "podman") — everything else (connection mode, socket path, host,
port) is the same shape either way. `_ENGINE_DEFAULTS` supplies the
per-engine connection defaults (Docker's standard local socket path is
`/var/run/docker.sock`; Podman's rootful socket is
`/run/podman/podman.sock` — rootless Podman users should override
`socket_path` to their own `$XDG_RUNTIME_DIR/podman/podman.sock`).
Switching `connection` to "tcp" targets a separate host's API instead,
unauthenticated over the LAN — same trusted-network assumption Pi-hole/
HDHomeRun make. Either way, get_summary/get_detail return a not-connected or
an error state rather than raising, so the widget degrades gracefully when
the daemon isn't reachable.
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.integrations import container_client
from app.plugins.base import Plugin, ToolDef

_ENGINE_DEFAULTS: dict[str, dict[str, Any]] = {
    "docker": {"socket_path": "/var/run/docker.sock", "host": "docker.local", "port": 2375},
    "podman": {"socket_path": "/run/podman/podman.sock", "host": "podman.local", "port": 8080},
}


class ContainerPlugin(Plugin):
    id = "container"
    name = "Container"
    refresh_interval_seconds = 30
    default_settings: ClassVar[dict[str, Any]] = {
        "engine": "docker",  # "docker" | "podman"
        "connection": "socket",  # "socket" | "tcp"
        "socket_path": "/var/run/docker.sock",
        "host": "",
        "port": 2375,
    }
    default_layout: ClassVar[dict[str, int]] = {"colSpan": 2, "rowSpan": 1}

    def _settings(self) -> dict[str, Any]:
        return self.config["settings"]

    def _engine(self) -> str:
        return self._settings().get("engine", "docker")

    def _is_connected(self) -> bool:
        return container_client.is_configured(self._settings())

    def _settings_view(self) -> dict[str, Any]:
        s = self._settings()
        engine = self._engine()
        engine_defaults = _ENGINE_DEFAULTS.get(engine, _ENGINE_DEFAULTS["docker"])
        return {
            "engine": engine,
            "connection": s.get("connection", "socket"),
            "socket_path": s.get("socket_path", engine_defaults["socket_path"]),
            "host": s.get("host", ""),
            "port": s.get("port", engine_defaults["port"]),
        }

    async def _containers(self) -> tuple[list[dict[str, Any]], str | None]:
        if not self._is_connected():
            return [], None
        try:
            containers = await container_client.fetch_containers(self._settings())
        except container_client.ContainerError as exc:
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
        engine = self._engine()

        async def get_container_status() -> dict[str, Any]:
            return await self.get_summary()

        return [
            ToolDef(
                name=f"get_{engine}_container_status",
                description=f"Get the list of {engine.capitalize()} containers on the configured host, their "
                "running/stopped state, and counts of running vs. stopped containers.",
                parameters={"type": "object", "properties": {}},
                handler=get_container_status,
            )
        ]
