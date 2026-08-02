"""HDHomeRun HTTP client for the HDHomeRun plugin.

Two independent, unauthenticated local-network devices are involved: the
tuner itself (channel lineup, per-tuner signal status) and, optionally, a
separate HDHomeRun DVR recording-engine service elsewhere on the LAN
(scheduled/in-progress recordings). Neither requires credentials, unlike
Jellyfin — there's nothing to mask in settings.

Program-guide data ("now playing" titles) is tried from two sources, in
order:
1. SiliconDust's cloud API (api.hdhomerun.com/api/guide.php), keyed by a
   `DeviceAuth` token from the tuner's own /discover.json — requires an
   active HDHomeRun DVR subscription.
2. A user-supplied XMLTV URL (`epg_url` setting) — the standard guide format
   used by Plex/Channels DVR/TVheadend/etc, for anyone without a
   subscription. Channels are matched by treating the XMLTV `<channel id>`
   as the HDHomeRun channel number directly.

Both treat any failure (no subscription, network error, unexpected shape) as
"unavailable" rather than raising, so the widget falls back to the plain
channel lineup instead of breaking.
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from xml.etree import ElementTree

import httpx

from app.storage.cache import cache

_GUIDE_URL = "https://api.hdhomerun.com/api/guide.php"
_DISCOVER_CACHE_TTL_SECONDS = 3600
_XMLTV_CACHE_TTL_SECONDS = 1800
_XMLTV_TIME_RE = re.compile(r"^(\d{14})(?:\s*([+-]\d{4}))?$")


class HDHomeRunError(Exception):
    """Raised when an HDHomeRun device can't be reached or rejects a request."""


def is_tuner_configured(settings: dict[str, Any]) -> bool:
    return bool(settings.get("tuner_host"))


def is_dvr_configured(settings: dict[str, Any]) -> bool:
    return bool(settings.get("dvr_host"))


def _normalize_host(host: str) -> str:
    # Users will naturally paste a full URL (with scheme and/or a trailing
    # slash) into a "host" field — strip that down to a bare hostname/IP
    # rather than building a malformed URL out of it.
    host = host.strip()
    for prefix in ("http://", "https://"):
        if host.startswith(prefix):
            host = host[len(prefix) :]
    return host.rstrip("/")


def _tuner_base_url(settings: dict[str, Any]) -> str:
    return f"http://{_normalize_host(settings['tuner_host'])}:{settings.get('tuner_port', 80)}"


def raw_stream_url(settings: dict[str, Any], channel_number: str) -> str:
    """The tuner's own raw MPEG-TS stream URL for a channel (port 5004,
    fixed by the HDHomeRun HTTP API — distinct from the discovery/JSON API
    port configured via `tuner_port`)."""
    host = _normalize_host(settings["tuner_host"])
    return f"http://{host}:5004/auto/v{channel_number}"


def _dvr_base_url(settings: dict[str, Any]) -> str:
    return f"http://{_normalize_host(settings['dvr_host'])}:{settings.get('dvr_port', 59090)}"


async def _get_json(url: str) -> Any:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
    except httpx.HTTPError as exc:
        raise HDHomeRunError(f"Could not reach {url}: {exc}") from exc
    if response.status_code >= 400:
        raise HDHomeRunError(f"Request to {url} failed (HTTP {response.status_code}).")
    try:
        return response.json()
    except ValueError as exc:
        # e.g. the wrong port is configured and it's returning something
        # other than JSON (a video stream, an HTML error page, etc).
        raise HDHomeRunError(f"Unexpected (non-JSON) response from {url}: {exc}") from exc


async def fetch_discover(settings: dict[str, Any]) -> dict[str, Any]:
    return await _get_json(f"{_tuner_base_url(settings)}/discover.json")


def _channel_dict(entry: dict[str, Any]) -> dict[str, Any]:
    tags = entry.get("Tags", "")
    return {
        "channel_number": entry.get("GuideNumber", ""),
        "name": entry.get("GuideName", ""),
        "is_hd": bool(entry.get("HD")) or "hd" in tags,
        "is_drm": bool(entry.get("DRM")) or "drm" in tags,
        "stream_url": entry.get("URL", ""),
    }


async def fetch_lineup(settings: dict[str, Any]) -> list[dict[str, Any]]:
    data = await _get_json(f"{_tuner_base_url(settings)}/lineup.json")
    return [_channel_dict(entry) for entry in data or []]


def _tuner_status_dict(entry: dict[str, Any], index: int) -> dict[str, Any]:
    # Field names vary by firmware/model and aren't fully documented — read
    # everything defensively so an unexpected shape degrades to missing
    # fields rather than raising.
    return {
        "index": index,
        "in_use": bool(entry.get("VctNumber") or entry.get("TargetIP")),
        "channel_number": entry.get("VctNumber"),
        "channel_name": entry.get("VctName"),
        "signal_strength_percent": entry.get("SignalStrengthPercent"),
        "signal_quality_percent": entry.get("SignalQualityPercent"),
        "symbol_quality_percent": entry.get("SymbolQualityPercent"),
        "network_rate_bps": entry.get("NetworkRate") or entry.get("NetworkRateBps"),
    }


async def fetch_tuner_status(settings: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        data = await _get_json(f"{_tuner_base_url(settings)}/status.json")
    except HDHomeRunError:
        return []
    if not isinstance(data, list):
        return []
    return [_tuner_status_dict(entry, index) for index, entry in enumerate(data)]


def _guide_entry_dict(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": entry.get("Title", ""),
        "episode_title": entry.get("EpisodeTitle"),
        "start": entry.get("StartTime"),
        "end": entry.get("EndTime"),
    }


async def fetch_guide(settings: dict[str, Any], widget_id: str) -> list[dict[str, Any]] | None:
    cache_key = f"hdhomerun_discover:{widget_id}"
    discover = cache.get(cache_key)
    if discover is None:
        try:
            discover = await fetch_discover(settings)
        except HDHomeRunError:
            return None
        cache.set(cache_key, discover, _DISCOVER_CACHE_TTL_SECONDS)

    device_auth = discover.get("DeviceAuth")
    if not device_auth:
        return None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(_GUIDE_URL, params={"DeviceAuth": device_auth})
        if response.status_code >= 400:
            return None
        data = response.json()
    except (httpx.HTTPError, ValueError):
        return None

    if not isinstance(data, list):
        return None

    now = time.time()
    result: list[dict[str, Any]] = []
    for channel in data:
        guide_entries = channel.get("Guide") or []
        current = next_up = None
        for entry in guide_entries:
            start, end = entry.get("StartTime"), entry.get("EndTime")
            if start is None or end is None:
                continue
            if start <= now < end:
                current = _guide_entry_dict(entry)
            elif start > now and next_up is None:
                next_up = _guide_entry_dict(entry)
        result.append({"channel_number": channel.get("GuideNumber", ""), "now": current, "next": next_up})
    return result


def _parse_xmltv_time(value: str | None) -> float | None:
    if not value:
        return None
    match = _XMLTV_TIME_RE.match(value.strip())
    if not match:
        return None
    dt_part, offset_part = match.groups()
    try:
        dt = datetime.strptime(dt_part, "%Y%m%d%H%M%S")
    except ValueError:
        return None
    if offset_part:
        sign = 1 if offset_part[0] == "+" else -1
        offset = sign * timedelta(hours=int(offset_part[1:3]), minutes=int(offset_part[3:5]))
        tz = timezone(offset)
    else:
        tz = UTC
    return dt.replace(tzinfo=tz).timestamp()


async def _fetch_and_parse_xmltv(epg_url: str) -> dict[str, list[dict[str, Any]]] | None:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(epg_url)
        if response.status_code >= 400:
            return None
        root = ElementTree.fromstring(response.content)
    except (httpx.HTTPError, ElementTree.ParseError):
        return None

    programmes_by_channel: dict[str, list[dict[str, Any]]] = {}
    for programme in root.findall("programme"):
        channel_id = programme.get("channel")
        start = _parse_xmltv_time(programme.get("start"))
        end = _parse_xmltv_time(programme.get("stop"))
        if channel_id is None or start is None or end is None:
            continue
        title_el = programme.find("title")
        subtitle_el = programme.find("sub-title")
        programmes_by_channel.setdefault(channel_id, []).append(
            {
                "start": start,
                "end": end,
                "title": (title_el.text or "") if title_el is not None else "",
                "episode_title": subtitle_el.text if subtitle_el is not None else None,
            }
        )
    return programmes_by_channel


async def fetch_xmltv_guide(settings: dict[str, Any], widget_id: str) -> list[dict[str, Any]] | None:
    epg_url = settings.get("epg_url")
    if not epg_url:
        return None

    cache_key = f"hdhomerun_xmltv:{widget_id}"
    programmes_by_channel = cache.get(cache_key)
    if programmes_by_channel is None:
        programmes_by_channel = await _fetch_and_parse_xmltv(epg_url)
        if programmes_by_channel is None:
            return None
        cache.set(cache_key, programmes_by_channel, _XMLTV_CACHE_TTL_SECONDS)

    now = time.time()
    result: list[dict[str, Any]] = []
    for channel_id, programmes in programmes_by_channel.items():
        current = next_up = None
        for entry in sorted(programmes, key=lambda p: p["start"]):
            if entry["start"] <= now < entry["end"]:
                current = {"title": entry["title"], "episode_title": entry["episode_title"]}
            elif entry["start"] > now and next_up is None:
                next_up = {"title": entry["title"], "episode_title": entry["episode_title"]}
        result.append({"channel_number": channel_id, "now": current, "next": next_up})
    return result


async def build_lineup_with_guide(settings: dict[str, Any], widget_id: str) -> tuple[list[dict[str, Any]], bool]:
    channels = await fetch_lineup(settings)
    guide = await fetch_guide(settings, widget_id)
    if guide is None:
        guide = await fetch_xmltv_guide(settings, widget_id)
    if guide is None:
        for channel in channels:
            channel["now"] = None
            channel["next"] = None
        return channels, False

    guide_by_channel = {entry["channel_number"]: entry for entry in guide}
    for channel in channels:
        match = guide_by_channel.get(channel["channel_number"])
        channel["now"] = match["now"] if match else None
        channel["next"] = match["next"] if match else None
    return channels, True


async def test_tuner_connection(settings: dict[str, Any]) -> str:
    discover = await fetch_discover(settings)
    return discover.get("FriendlyName", "HDHomeRun")


async def test_dvr_connection(settings: dict[str, Any]) -> str:
    discover = await _get_json(f"{_dvr_base_url(settings)}/discover.json")
    return discover.get("FriendlyName", "HDHomeRun DVR")


async def fetch_dvr_info(settings: dict[str, Any]) -> dict[str, Any]:
    discover = await _get_json(f"{_dvr_base_url(settings)}/discover.json")
    return {
        "friendly_name": discover.get("FriendlyName", "HDHomeRun DVR"),
        "version": discover.get("Version"),
        "free_space_bytes": discover.get("FreeSpace"),
    }


def _recording_dict(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": entry.get("Title", ""),
        "channel_name": entry.get("ChannelAffiliate") or entry.get("ChannelName"),
        "start": entry.get("StartTime") or entry.get("RecordStartTime"),
        "record_end": entry.get("RecordEndTime"),
    }


async def fetch_dvr_recordings(settings: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        discover = await _get_json(f"{_dvr_base_url(settings)}/discover.json")
        storage_url = discover.get("StorageURL")
        if not storage_url:
            return []
        data = await _get_json(storage_url)
    except HDHomeRunError:
        return []
    if not isinstance(data, list):
        return []
    return [_recording_dict(entry) for entry in data]


async def fetch_dvr_recording_rules(settings: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        data = await _get_json(f"{_dvr_base_url(settings)}/recording_rules.json")
    except HDHomeRunError:
        return []
    if not isinstance(data, list):
        return []
    return data
