from __future__ import annotations

import httpx
import respx

from app.plugins.synology.plugin import SynologyPlugin

CONNECTED_SETTINGS = {
    "host": "syno.local",
    "port": 5000,
    "use_https": False,
    "username": "admin",
    "password": "secret",
}

AUTH_OK = {"success": True, "data": {"sid": "sid1"}}

STORAGE_RESPONSE = {
    "success": True,
    "data": {
        "volumes": [
            {"id": "volume_1", "desc": "Volume 1", "status": "normal", "size": {"total": "1000", "used": "250"}},
            {"id": "volume_2", "desc": "Volume 2", "status": "warning", "size": {"total": "2000", "used": "1800"}},
        ]
    },
}

SYSTEM_INFO_RESPONSE = {
    "success": True,
    "data": {"model": "DS920+", "up_time": "12:34:56", "temperature": 42},
}


def make_plugin(**settings) -> SynologyPlugin:
    return SynologyPlugin({"id": "synology", "settings": {**SynologyPlugin.default_settings, **settings}})


async def test_get_summary_when_not_configured():
    plugin = make_plugin(host="")

    summary = await plugin.get_summary()

    assert summary["connected"] is False
    assert summary["volumes"] == []
    assert summary["has_password"] is False


async def test_get_summary_masks_password():
    plugin = make_plugin(**CONNECTED_SETTINGS)

    summary = await plugin.get_summary()

    assert "password" not in summary
    assert summary["has_password"] is True


@respx.mock
async def test_get_summary_when_connected_reports_volumes():
    respx.get("http://syno.local:5000/webapi/auth.cgi").mock(return_value=httpx.Response(200, json=AUTH_OK))
    respx.get("http://syno.local:5000/webapi/entry.cgi").mock(return_value=httpx.Response(200, json=STORAGE_RESPONSE))
    plugin = make_plugin(**CONNECTED_SETTINGS)

    summary = await plugin.get_summary()

    assert summary["connected"] is True
    assert summary["volumes"] == [
        {"name": "Volume 1", "used_percent": 25.0, "status": "normal"},
        {"name": "Volume 2", "used_percent": 90.0, "status": "warning"},
    ]


@respx.mock
async def test_get_summary_surfaces_error_without_raising():
    respx.get("http://syno.local:5000/webapi/auth.cgi").mock(side_effect=httpx.ConnectError("refused"))
    plugin = make_plugin(**CONNECTED_SETTINGS)

    summary = await plugin.get_summary()

    assert summary["connected"] is True
    assert "error" in summary
    assert summary["volumes"] == []


async def test_get_detail_when_not_configured():
    plugin = make_plugin(host="")

    detail = await plugin.get_detail()

    assert detail["connected"] is False
    assert detail["volumes"] == []
    assert detail["model"] is None
    assert detail["uptime"] is None
    assert detail["temperature_celsius"] is None


@respx.mock
async def test_get_detail_when_connected_reports_volumes_and_system_info():
    respx.get("http://syno.local:5000/webapi/auth.cgi").mock(return_value=httpx.Response(200, json=AUTH_OK))
    respx.get("http://syno.local:5000/webapi/entry.cgi").mock(
        side_effect=[
            # get_detail calls get_summary() (1 storage fetch) then re-fetches
            # storage itself before the system-info call.
            httpx.Response(200, json=STORAGE_RESPONSE),
            httpx.Response(200, json=STORAGE_RESPONSE),
            httpx.Response(200, json=SYSTEM_INFO_RESPONSE),
        ]
    )
    plugin = make_plugin(**CONNECTED_SETTINGS)

    detail = await plugin.get_detail()

    assert detail["connected"] is True
    assert detail["volumes"] == [
        {"name": "Volume 1", "total_bytes": 1000, "used_bytes": 250, "used_percent": 25.0, "status": "normal"},
        {"name": "Volume 2", "total_bytes": 2000, "used_bytes": 1800, "used_percent": 90.0, "status": "warning"},
    ]
    assert detail["model"] == "DS920+"
    assert detail["uptime"] == "12:34:56"
    assert detail["temperature_celsius"] == 42


@respx.mock
async def test_get_detail_surfaces_storage_error_without_raising():
    respx.get("http://syno.local:5000/webapi/auth.cgi").mock(side_effect=httpx.ConnectError("refused"))
    plugin = make_plugin(**CONNECTED_SETTINGS)

    detail = await plugin.get_detail()

    assert detail["connected"] is True
    assert "error" in detail
    assert detail["volumes"] == []
    assert detail["model"] is None


@respx.mock
async def test_get_detail_surfaces_system_info_error_without_raising():
    respx.get("http://syno.local:5000/webapi/auth.cgi").mock(return_value=httpx.Response(200, json=AUTH_OK))
    respx.get("http://syno.local:5000/webapi/entry.cgi").mock(
        side_effect=[
            httpx.Response(200, json=STORAGE_RESPONSE),
            httpx.Response(200, json=STORAGE_RESPONSE),
            httpx.ConnectError("refused"),
        ]
    )
    plugin = make_plugin(**CONNECTED_SETTINGS)

    detail = await plugin.get_detail()

    assert detail["connected"] is True
    assert "error" in detail
    assert detail["volumes"] == [
        {"name": "Volume 1", "total_bytes": 1000, "used_bytes": 250, "used_percent": 25.0, "status": "normal"},
        {"name": "Volume 2", "total_bytes": 2000, "used_bytes": 1800, "used_percent": 90.0, "status": "warning"},
    ]
    assert detail["model"] is None


async def test_get_ai_tools_returns_storage_status_tool():
    plugin = make_plugin(host="")

    tools = plugin.get_ai_tools()

    assert len(tools) == 1
    assert tools[0].name == "get_synology_storage_status"
    result = await tools[0].handler()
    assert result["connected"] is False
