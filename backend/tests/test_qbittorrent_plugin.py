from __future__ import annotations

import httpx
import respx

from app.plugins.qbittorrent.plugin import QBittorrentPlugin

MAINDATA_RESPONSE = {
    "torrents": {
        "hash1": {
            "name": "Ubuntu ISO",
            "state": "downloading",
            "progress": 0.5,
            "size": 4_000_000_000,
            "dlspeed": 1_000_000,
            "upspeed": 0,
            "eta": 3600,
        },
        "hash2": {
            "name": "Debian ISO",
            "state": "uploading",
            "progress": 1.0,
            "size": 3_000_000_000,
            "dlspeed": 0,
            "upspeed": 500_000,
            "eta": 8640000,
        },
    },
    "server_state": {"dl_info_speed": 1_000_000, "up_info_speed": 500_000},
}


def make_plugin(**settings) -> QBittorrentPlugin:
    return QBittorrentPlugin({"id": "qb1", "settings": {**QBittorrentPlugin.default_settings, **settings}})


async def test_get_summary_when_not_configured():
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["connected"] is False
    assert summary["has_password"] is False


async def test_get_summary_echoes_settings():
    plugin = make_plugin(host="qbit.local", port=8080, username="me", password="secret")

    summary = await plugin.get_summary()

    assert summary["host"] == "qbit.local"
    assert summary["username"] == "me"
    assert summary["has_password"] is True
    # password itself is never echoed back
    assert "password" not in summary


@respx.mock
async def test_get_summary_reports_torrent_counts_and_speed():
    plugin = make_plugin(host="qbit.local", password="secret")
    respx.post("http://qbit.local:8080/api/v2/auth/login").mock(
        return_value=httpx.Response(200, text="Ok.", headers={"Set-Cookie": "SID=abc123; Path=/"})
    )
    respx.get("http://qbit.local:8080/api/v2/sync/maindata").mock(
        return_value=httpx.Response(200, json=MAINDATA_RESPONSE)
    )

    summary = await plugin.get_summary()

    assert summary["connected"] is True
    assert summary["torrent_count"] == 2
    assert summary["downloading_count"] == 1
    assert summary["seeding_count"] == 1
    assert summary["download_speed_bps"] == 1_000_000
    assert summary["upload_speed_bps"] == 500_000


@respx.mock
async def test_get_detail_returns_sorted_torrent_list():
    plugin = make_plugin(host="qbit.local", password="secret")
    respx.post("http://qbit.local:8080/api/v2/auth/login").mock(
        return_value=httpx.Response(200, text="Ok.", headers={"Set-Cookie": "SID=abc123; Path=/"})
    )
    respx.get("http://qbit.local:8080/api/v2/sync/maindata").mock(
        return_value=httpx.Response(200, json=MAINDATA_RESPONSE)
    )

    detail = await plugin.get_detail()

    assert detail["connected"] is True
    assert len(detail["torrents"]) == 2
    # sorted by download speed descending
    assert detail["torrents"][0]["name"] == "Ubuntu ISO"
    assert detail["torrents"][1]["name"] == "Debian ISO"


async def test_get_detail_when_not_configured():
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["connected"] is False
    assert detail["torrents"] == []


@respx.mock
async def test_get_summary_degrades_gracefully_on_error():
    plugin = make_plugin(host="qbit.local", password="wrong")
    respx.post("http://qbit.local:8080/api/v2/auth/login").mock(return_value=httpx.Response(200, text="Fails."))

    summary = await plugin.get_summary()

    assert summary["connected"] is True
    assert summary["error"]
