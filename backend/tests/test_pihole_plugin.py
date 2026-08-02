from __future__ import annotations

import httpx
import respx

from app.plugins.pihole.plugin import PiholePlugin

CONNECTED_SETTINGS = {"host": "pi.local", "port": 80, "use_https": False, "password": "secret"}

AUTH_OK = {"session": {"valid": True, "sid": "sid1", "csrf": "csrf1", "validity": 1800}}
SUMMARY_RESPONSE = {
    "queries": {"total": 1000, "blocked": 250, "percent_blocked": 25.0},
    "clients": {"active": 4, "total": 6},
    "gravity": {"domains_being_blocked": 999999, "last_update": 1700000000},
}


def make_plugin(**settings) -> PiholePlugin:
    return PiholePlugin({"id": "pihole", "settings": {**PiholePlugin.default_settings, **settings}})


async def test_get_summary_when_not_configured():
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["connected"] is False
    assert summary["has_password"] is False


async def test_get_summary_echoes_and_masks_settings():
    plugin = make_plugin(host="pi.local", password="secret")

    summary = await plugin.get_summary()

    assert summary["host"] == "pi.local"
    assert summary["has_password"] is True
    assert "password" not in summary


@respx.mock
async def test_get_summary_when_connected():
    respx.post("http://pi.local:80/api/auth").mock(return_value=httpx.Response(200, json=AUTH_OK))
    respx.get("http://pi.local:80/api/stats/summary").mock(return_value=httpx.Response(200, json=SUMMARY_RESPONSE))
    respx.get("http://pi.local:80/api/dns/blocking").mock(
        return_value=httpx.Response(200, json={"blocking": "enabled", "timer": None})
    )
    plugin = make_plugin(**CONNECTED_SETTINGS)

    summary = await plugin.get_summary()

    assert summary["connected"] is True
    assert summary["blocking_enabled"] is True
    assert summary["queries_today"] == 1000
    assert summary["blocked_today"] == 250
    assert summary["percent_blocked"] == 25.0


@respx.mock
async def test_get_summary_surfaces_error_without_raising():
    respx.post("http://pi.local:80/api/auth").mock(return_value=httpx.Response(200, json=AUTH_OK))
    respx.get("http://pi.local:80/api/stats/summary").mock(return_value=httpx.Response(500))
    respx.get("http://pi.local:80/api/dns/blocking").mock(
        return_value=httpx.Response(200, json={"blocking": "enabled", "timer": None})
    )
    plugin = make_plugin(**CONNECTED_SETTINGS)

    summary = await plugin.get_summary()

    assert summary["connected"] is True
    assert "error" in summary


@respx.mock
async def test_get_detail_includes_top_domains_and_gravity():
    respx.post("http://pi.local:80/api/auth").mock(return_value=httpx.Response(200, json=AUTH_OK))
    respx.get("http://pi.local:80/api/stats/summary").mock(return_value=httpx.Response(200, json=SUMMARY_RESPONSE))
    respx.get("http://pi.local:80/api/dns/blocking").mock(
        return_value=httpx.Response(200, json={"blocking": "enabled", "timer": None})
    )
    respx.get("http://pi.local:80/api/stats/top_domains", params={"blocked": "true"}).mock(
        return_value=httpx.Response(200, json={"domains": [{"domain": "ads.example.com", "count": 42}]})
    )
    respx.get("http://pi.local:80/api/stats/top_domains", params={"blocked": "false"}).mock(
        return_value=httpx.Response(200, json={"domains": [{"domain": "example.com", "count": 100}]})
    )
    plugin = make_plugin(**CONNECTED_SETTINGS)

    detail = await plugin.get_detail()

    assert detail["unique_clients"] == 4
    assert detail["clients_total"] == 6
    assert detail["domains_blocked"] == 999999
    assert detail["gravity_last_update"] == 1700000000
    assert detail["top_blocked_domains"] == [{"domain": "ads.example.com", "count": 42}]
    assert detail["top_permitted_domains"] == [{"domain": "example.com", "count": 100}]


async def test_get_detail_when_not_configured():
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["connected"] is False
    assert detail["top_blocked_domains"] == []
    assert detail["top_permitted_domains"] == []


async def test_get_ai_tools_returns_summary_tool():
    plugin = make_plugin()

    tools = plugin.get_ai_tools()

    assert len(tools) == 1
    assert tools[0].name == "get_pihole_summary"
    result = await tools[0].handler()
    assert result["connected"] is False
