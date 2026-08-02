from __future__ import annotations

import httpx
import respx

from app.plugins.asus_router.plugin import AsusRouterPlugin

CONNECTED_SETTINGS = {
    "host": "router.local",
    "port": 443,
    "use_https": True,
    "username": "admin",
    "password": "secret",
}

LOGIN_OK = {"asus_token": "tok"}

CLIENTLIST_RESPONSE = {
    "get_clientlist": {
        "AA:BB:CC:DD:EE:FF": {"nickName": "Laptop", "ip": "192.168.1.10", "isOnline": "1"},
        "maclist": ["AA:BB:CC:DD:EE:FF"],
    }
}

WAN_RESPONSE = {"wanlink_statusstr": "Connected", "wanlink_ipaddr": "203.0.113.5"}

TRAFFIC_RESPONSE = {"netdev": {"INTERNET_rx": "1024", "INTERNET_tx": "512"}}


def make_plugin(**settings) -> AsusRouterPlugin:
    return AsusRouterPlugin({"id": "asus_router", "settings": {**AsusRouterPlugin.default_settings, **settings}})


async def test_get_summary_when_not_configured():
    plugin = make_plugin(host="")

    summary = await plugin.get_summary()

    assert summary["connected"] is False
    assert summary["wan_connected"] is False
    assert summary["client_count"] == 0
    assert summary["has_password"] is False


async def test_get_summary_masks_password():
    plugin = make_plugin(**CONNECTED_SETTINGS)

    summary = await plugin.get_summary()

    assert "password" not in summary
    assert summary["has_password"] is True


@respx.mock
async def test_get_summary_when_connected_reports_wan_and_client_count():
    respx.post("https://router.local:443/login.cgi").mock(return_value=httpx.Response(200, json=LOGIN_OK))
    respx.post("https://router.local:443/appGet.cgi").mock(
        side_effect=[
            httpx.Response(200, json=WAN_RESPONSE),
            httpx.Response(200, json=CLIENTLIST_RESPONSE),
        ]
    )
    plugin = make_plugin(**CONNECTED_SETTINGS)

    summary = await plugin.get_summary()

    assert summary["connected"] is True
    assert summary["wan_connected"] is True
    assert summary["client_count"] == 1


@respx.mock
async def test_get_summary_surfaces_error_without_raising():
    respx.post("https://router.local:443/login.cgi").mock(side_effect=httpx.ConnectError("refused"))
    plugin = make_plugin(**CONNECTED_SETTINGS)

    summary = await plugin.get_summary()

    assert summary["connected"] is True
    assert "error" in summary
    assert summary["client_count"] == 0


async def test_get_detail_when_not_configured():
    plugin = make_plugin(host="")

    detail = await plugin.get_detail()

    assert detail["connected"] is False
    assert detail["clients"] == []
    assert detail["wan_ip"] is None
    assert detail["rx_bytes"] == 0
    assert detail["tx_bytes"] == 0


@respx.mock
async def test_get_detail_when_connected_reports_clients_and_traffic():
    respx.post("https://router.local:443/login.cgi").mock(return_value=httpx.Response(200, json=LOGIN_OK))
    respx.post("https://router.local:443/appGet.cgi").mock(
        side_effect=[
            # get_detail calls get_summary() (wan + clients) then re-fetches
            # wan + clients itself before the traffic call.
            httpx.Response(200, json=WAN_RESPONSE),
            httpx.Response(200, json=CLIENTLIST_RESPONSE),
            httpx.Response(200, json=WAN_RESPONSE),
            httpx.Response(200, json=CLIENTLIST_RESPONSE),
            httpx.Response(200, json=TRAFFIC_RESPONSE),
        ]
    )
    plugin = make_plugin(**CONNECTED_SETTINGS)

    detail = await plugin.get_detail()

    assert detail["connected"] is True
    assert detail["wan_ip"] == "203.0.113.5"
    assert detail["clients"] == [{"name": "Laptop", "ip": "192.168.1.10", "online": True}]
    assert detail["rx_bytes"] == 1024
    assert detail["tx_bytes"] == 512


@respx.mock
async def test_get_detail_surfaces_wan_error_without_raising():
    respx.post("https://router.local:443/login.cgi").mock(side_effect=httpx.ConnectError("refused"))
    plugin = make_plugin(**CONNECTED_SETTINGS)

    detail = await plugin.get_detail()

    assert detail["connected"] is True
    assert "error" in detail
    assert detail["clients"] == []
    assert detail["wan_ip"] is None


@respx.mock
async def test_get_detail_surfaces_traffic_error_without_raising():
    respx.post("https://router.local:443/login.cgi").mock(return_value=httpx.Response(200, json=LOGIN_OK))
    respx.post("https://router.local:443/appGet.cgi").mock(
        side_effect=[
            httpx.Response(200, json=WAN_RESPONSE),
            httpx.Response(200, json=CLIENTLIST_RESPONSE),
            httpx.Response(200, json=WAN_RESPONSE),
            httpx.Response(200, json=CLIENTLIST_RESPONSE),
            httpx.ConnectError("refused"),
        ]
    )
    plugin = make_plugin(**CONNECTED_SETTINGS)

    detail = await plugin.get_detail()

    assert detail["connected"] is True
    assert "error" in detail
    assert detail["wan_ip"] == "203.0.113.5"
    assert detail["clients"] == [{"name": "Laptop", "ip": "192.168.1.10", "online": True}]
    assert detail["rx_bytes"] == 0
    assert detail["tx_bytes"] == 0


async def test_get_ai_tools_returns_status_tool():
    plugin = make_plugin(host="")

    tools = plugin.get_ai_tools()

    assert len(tools) == 1
    assert tools[0].name == "get_asus_router_status"
    result = await tools[0].handler()
    assert result["connected"] is False
