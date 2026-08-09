"""HDHomeRun plugin: channel lineup, tuner/device status, and (optionally) a
separate HDHomeRun DVR recording engine's recording status.

Both the tuner and the DVR recording engine are unauthenticated local-network
devices, so unlike Jellyfin there are no secrets to mask in settings. The two
connections are independent — the tuner can be configured/reachable while
the DVR engine isn't (or vice versa), so each has its own connected state.
Program-guide data ("now playing" titles) prefers SiliconDust's cloud API,
which needs a working HDHomeRun DVR subscription behind the scenes; failing
that, a user-supplied XMLTV `epg_url` is tried instead; if neither is
available, the widget falls back to the plain channel lineup rather than
erroring (see `app/integrations/hdhomerun_client.build_lineup_with_guide`).

In-app playback is possible, but the raw tuner stream never is: HDHomeRun
tuners stream MPEG-2 (US ATSC OTA) inside MPEG-TS, and no browser can decode
MPEG-2 via Media Source Extensions. Each channel's `playback_url` is derived
from `playback_mode` instead:

- "server_transcode" (default): this backend spawns `ffmpeg` to transcode
  the raw stream to H.264/AAC (see `app/api/hdhomerun.py`'s `/stream`
  route) — works on any tuner, at the cost of real CPU on whatever machine
  runs the backend. Which ffmpeg arguments it uses is controlled by the
  `hwaccel` setting (a preset id from `app/transcoding.py`, or "custom" to
  supply raw arguments via `custom_ffmpeg_args`) — different backend hosts
  benefit from different hardware encoders, so this isn't one-size-fits-all.
- "external": no `playback_url` at all — channels only offer a raw-stream
  link (via the `/playlist` route) for opening in VLC/mpv etc.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app import transcoding
from app.integrations import hdhomerun_client
from app.plugins.base import Plugin, ToolDef

logger = logging.getLogger(__name__)


class HDHomeRunPlugin(Plugin):
    id = "hdhomerun"
    name = "HDHomeRun"
    refresh_interval_seconds = 120
    network_integration_type = "hdhomerun"
    network_default_settings = {
        "tuner_host": "",
        "tuner_port": 80,
        "dvr_host": "",
        "dvr_port": 59090,
        "epg_url": "",
    }
    default_settings = {
        # "server_transcode" | "external" — see the module docstring for
        # the tradeoffs of each.
        "playback_mode": "server_transcode",
        # ffmpeg transcode preset id from app/transcoding.py's
        # TRANSCODE_PRESETS (only used when playback_mode is
        # "server_transcode"), or "custom" to use custom_ffmpeg_args instead.
        "hwaccel": transcoding.DEFAULT_PRESET,
        # Raw ffmpeg output arguments, only used when hwaccel == "custom".
        "custom_ffmpeg_args": "",
        # DRM render node the VAAPI/QSV presets bind to. Not always
        # /dev/dri/renderD128 — a second DRM device shifts the iGPU's node to
        # renderD129 — so it has to be settable rather than hardcoded. The
        # hardware-acceleration diagnostics list what's actually present.
        "hwaccel_device": transcoding.DEFAULT_HWACCEL_DEVICE,
        # Raise ffmpeg's own log level from "warning" to "verbose", so the
        # backend log shows hwaccel device init and filter-graph format
        # negotiation. Off by default: it's several lines per second per
        # viewer.
        "ffmpeg_debug": False,
        # Channel numbers (e.g. "4.1") the user has starred on the detail
        # page. Empty means "no preference yet" — the tile summary falls
        # back to showing whatever channels happen to have guide data,
        # rather than showing nothing until the user picks favorites.
        "favorite_channels": [],
    }
    default_layout = {"colSpan": 2, "rowSpan": 1}

    def validate_settings(self, payload: dict[str, Any]) -> None:
        # An unrecognised hwaccel id silently falls back to the software
        # preset (transcoding.resolve_preset), so a typo used to look like
        # "hardware acceleration is on but has no effect" — indistinguishable
        # from a GPU problem, and invisible in the logs.
        if "hwaccel" in payload and payload["hwaccel"] not in transcoding.TRANSCODE_PRESETS:
            valid = ", ".join(sorted(transcoding.TRANSCODE_PRESETS))
            raise ValueError(f"Unknown hwaccel preset '{payload['hwaccel']}'. Valid presets: {valid}")

    def _settings(self) -> dict[str, Any]:
        return self.config["settings"]

    def _favorite_channels(self) -> list[str]:
        return self._settings().get("favorite_channels") or []

    def _tuner_connected(self) -> bool:
        return hdhomerun_client.is_tuner_configured(self._settings())

    def _dvr_connected(self) -> bool:
        return hdhomerun_client.is_dvr_configured(self._settings())

    async def _channels(self) -> tuple[list[dict[str, Any]], bool]:
        if not self._tuner_connected():
            return [], False
        try:
            channels, guide_available = await hdhomerun_client.build_lineup_with_guide(self._settings(), self.id)
        except hdhomerun_client.HDHomeRunError:
            logger.warning("Could not build channel lineup for HDHomeRun widget '%s'", self.id, exc_info=True)
            return [], False
        for channel in channels:
            channel["playback_url"] = self._playback_url(channel)
        return channels, guide_available

    def _playback_url(self, channel: dict[str, Any]) -> str | None:
        mode = self._settings().get("playback_mode", "server_transcode")
        if mode == "server_transcode":
            return f"/api/hdhomerun/{self.id}/stream/{channel['channel_number']}"
        return None

    async def _recordings_in_progress(self) -> list[dict[str, Any]]:
        if not self._dvr_connected():
            return []
        recordings = await hdhomerun_client.fetch_dvr_recordings(self._settings())
        now = time.time()
        # recorded_files.json doesn't clearly distinguish "still recording"
        # from "finished" in the documented shape — a future record_end is
        # the best available signal; entries missing one are treated as
        # already-completed recordings rather than assumed in-progress.
        return [r for r in recordings if r["record_end"] is not None and r["record_end"] > now]

    async def get_summary(self) -> dict[str, Any]:
        channels, guide_available = await self._channels()
        favorites = self._favorite_channels()
        # Favorites narrow which channels' "now playing" shows on the tile,
        # but channel_count still reflects the full lineup size.
        now_playing_channels = [c for c in channels if c["channel_number"] in favorites] if favorites else channels
        now_playing = [
            {
                "channel_number": c["channel_number"],
                "channel_name": c["name"],
                "title": c["now"]["title"],
                "episode_title": c["now"]["episode_title"],
            }
            for c in now_playing_channels
            if c.get("now")
        ]
        if not favorites:
            # No favorites picked yet — cap the noisy full-lineup fallback;
            # favorites are an explicit user choice, so show all of them.
            now_playing = now_playing[:3]
        recordings = await self._recordings_in_progress()
        return {
            "tuner_connected": self._tuner_connected(),
            "dvr_connected": self._dvr_connected(),
            "channel_count": len(channels),
            "guide_available": guide_available,
            "now_playing": now_playing,
            "active_recordings_count": len(recordings),
            **self._settings_view(),
        }

    def _settings_view(self) -> dict[str, Any]:
        s = self._settings()
        return {
            "tuner_host": s.get("tuner_host", ""),
            "tuner_port": s.get("tuner_port", 80),
            "dvr_host": s.get("dvr_host", ""),
            "dvr_port": s.get("dvr_port", 59090),
            "epg_url": s.get("epg_url", ""),
            "playback_mode": s.get("playback_mode", "server_transcode"),
            "hwaccel": s.get("hwaccel", transcoding.DEFAULT_PRESET),
            "custom_ffmpeg_args": s.get("custom_ffmpeg_args", ""),
            "hwaccel_device": transcoding.resolve_device(s),
            "ffmpeg_debug": bool(s.get("ffmpeg_debug", False)),
            "favorite_channels": s.get("favorite_channels") or [],
            # The exact ffmpeg command server_transcode playback will run —
            # always surfaced so the user can see what their hwaccel choice
            # actually does, rather than trusting a hidden default.
            "ffmpeg_command": transcoding.command_preview(s),
        }

    async def get_detail(self) -> dict[str, Any]:
        channels, guide_available = await self._channels()

        tuner_info = None
        tuners: list[dict[str, Any]] = []
        if self._tuner_connected():
            try:
                discover = await hdhomerun_client.fetch_discover(self._settings())
                tuner_info = {
                    "friendly_name": discover.get("FriendlyName", "HDHomeRun"),
                    "model_number": discover.get("ModelNumber"),
                    "firmware_version": discover.get("FirmwareVersion"),
                    "tuner_count": discover.get("TunerCount"),
                }
            except hdhomerun_client.HDHomeRunError:
                logger.warning("Could not fetch tuner discover info for HDHomeRun widget '%s'", self.id, exc_info=True)
                tuner_info = None
            tuners = await hdhomerun_client.fetch_tuner_status(self._settings())

        dvr_info = None
        recording_rules: list[dict[str, Any]] = []
        if self._dvr_connected():
            try:
                dvr_info = await hdhomerun_client.fetch_dvr_info(self._settings())
            except hdhomerun_client.HDHomeRunError:
                logger.warning("Could not fetch DVR info for HDHomeRun widget '%s'", self.id, exc_info=True)
                dvr_info = None
            recording_rules = await hdhomerun_client.fetch_dvr_recording_rules(self._settings())

        return {
            "tuner_connected": self._tuner_connected(),
            "dvr_connected": self._dvr_connected(),
            "guide_available": guide_available,
            "tuner_info": tuner_info,
            "channels": channels,
            "tuners": tuners,
            "dvr_info": dvr_info,
            "recordings_in_progress": await self._recordings_in_progress(),
            "upcoming_recording_rules_count": len(recording_rules),
            **self._settings_view(),
        }

    def get_ai_tools(self) -> list[ToolDef]:
        async def get_now_playing(channel: str | None = None) -> dict[str, Any]:
            detail = await self.get_detail()
            channels = detail["channels"]
            if channel:
                channels = [c for c in channels if c["channel_number"] == channel]
            return {
                "guide_available": detail["guide_available"],
                "channels": [
                    {"channel_number": c["channel_number"], "name": c["name"], "now": c["now"], "next": c["next"]}
                    for c in channels
                ],
            }

        async def get_active_recordings() -> dict[str, Any]:
            detail = await self.get_detail()
            return {
                "dvr_connected": detail["dvr_connected"],
                "recordings_in_progress": detail["recordings_in_progress"],
            }

        return [
            ToolDef(
                name="get_now_playing",
                description="Get what's currently airing on the HDHomeRun tuner's channels (optionally one channel).",
                parameters={
                    "type": "object",
                    "properties": {
                        "channel": {
                            "type": "string",
                            "description": "Channel number, e.g. '4.1'. Omit for all channels.",
                        }
                    },
                    "required": [],
                },
                handler=get_now_playing,
            ),
            ToolDef(
                name="get_active_recordings",
                description="Check whether the HDHomeRun DVR is currently recording anything.",
                parameters={"type": "object", "properties": {}},
                handler=get_active_recordings,
            ),
        ]
