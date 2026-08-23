"""qBittorrent plugin: active torrent count, queue, and transfer speed from a
qBittorrent WebUI instance.

Connects via the WebUI username/password (see
`app/integrations/qbittorrent_client.py` for the session-auth flow); until
connected, get_summary/get_detail return a not-connected state rather than
raising, so the widget degrades gracefully.
"""

from __future__ import annotations

import logging
from typing import Any

from app.integrations import qbittorrent_client
from app.plugins.base import Plugin, ToolDef

logger = logging.getLogger(__name__)

# qBittorrent torrent states that count as "actively downloading" vs
# "seeding" for the tile's at-a-glance counts — see qBittorrent's WebUI API
# docs for the full state enum (stalledDL/metaDL/checkingDL/forcedDL also
# count as downloading; the torrent just isn't transferring at that instant).
_DOWNLOADING_STATES = {"downloading", "stalledDL", "metaDL", "checkingDL", "forcedDL", "allocating"}
_SEEDING_STATES = {"uploading", "stalledUP", "checkingUP", "forcedUP"}


class QBittorrentPlugin(Plugin):
    id = "qbittorrent"
    name = "qBittorrent"
    refresh_interval_seconds = 30
    default_settings = {
        "host": "",
        "port": 8080,
        "use_https": False,
        "username": "admin",
        "password": "",
    }
    secret_setting_keys = frozenset({"password"})

    def _is_connected(self) -> bool:
        return qbittorrent_client.is_configured(self.config["settings"])

    async def _maindata(self) -> dict[str, Any]:
        settings = self.config["settings"]
        try:
            data = await qbittorrent_client.get_maindata(settings, self.id)
        except qbittorrent_client.QBittorrentError as exc:
            logger.warning("Could not fetch qBittorrent data for widget '%s': %s", self.id, exc)
            return {"error": str(exc)}

        torrents = data.get("torrents") or {}
        server_state = data.get("server_state") or {}
        downloading = sum(1 for t in torrents.values() if t.get("state") in _DOWNLOADING_STATES)
        seeding = sum(1 for t in torrents.values() if t.get("state") in _SEEDING_STATES)
        return {
            "torrent_count": len(torrents),
            "downloading_count": downloading,
            "seeding_count": seeding,
            "download_speed_bps": server_state.get("dl_info_speed", 0),
            "upload_speed_bps": server_state.get("up_info_speed", 0),
            "_torrents": torrents,
        }

    async def get_summary(self) -> dict[str, Any]:
        connected = self._is_connected()
        stats: dict[str, Any] = {}
        if connected:
            stats = await self._maindata()
            stats.pop("_torrents", None)
        return {"connected": connected, **stats, **self._safe_settings()}

    async def get_detail(self) -> dict[str, Any]:
        connected = self._is_connected()
        if not connected:
            return {"connected": False, "torrents": [], **self._safe_settings()}

        stats = await self._maindata()
        torrents_raw = stats.pop("_torrents", {})
        if stats.get("error"):
            return {"connected": True, "torrents": [], **stats, **self._safe_settings()}

        torrents = [
            {
                "hash": torrent_hash,
                "name": t.get("name", ""),
                "state": t.get("state", ""),
                "progress": t.get("progress", 0),
                "size_bytes": t.get("size", 0),
                "download_speed_bps": t.get("dlspeed", 0),
                "upload_speed_bps": t.get("upspeed", 0),
                "eta_seconds": t.get("eta"),
            }
            for torrent_hash, t in torrents_raw.items()
        ]
        torrents.sort(key=lambda t: t["download_speed_bps"], reverse=True)
        return {"connected": True, "torrents": torrents, **stats, **self._safe_settings()}

    def get_ai_tools(self) -> list[ToolDef]:
        async def get_qbittorrent_summary() -> dict[str, Any]:
            return await self.get_summary()

        return [
            ToolDef(
                name="get_qbittorrent_summary",
                description="Get the current qBittorrent torrent counts (total/downloading/seeding) and "
                "aggregate download/upload speed.",
                parameters={"type": "object", "properties": {}},
                handler=get_qbittorrent_summary,
            )
        ]
