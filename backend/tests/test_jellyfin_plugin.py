from __future__ import annotations

import httpx
import respx

from app.plugins.jellyfin.plugin import JellyfinPlugin


def make_plugin(**settings) -> JellyfinPlugin:
    return JellyfinPlugin({"id": "jellyfin", "settings": {**JellyfinPlugin.default_settings, **settings}})


async def test_get_summary_when_not_connected():
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["connected"] is False
    assert summary["recent_items"] == []


async def test_get_detail_never_leaks_api_key_or_password():
    plugin = make_plugin(api_key="super-secret", password="also-secret", username="alice")

    detail = await plugin.get_detail()

    assert "api_key" not in detail
    assert "password" not in detail
    assert detail["has_api_key"] is True
    assert detail["has_password"] is True
    assert detail["username"] == "alice"


async def test_get_summary_never_leaks_api_key_or_password():
    plugin = make_plugin(api_key="super-secret", password="also-secret")

    summary = await plugin.get_summary()

    assert "api_key" not in summary
    assert "password" not in summary


@respx.mock
async def test_get_summary_connected_includes_recent_items():
    respx.get("http://jf.local:8096/Items", params={"Recursive": "true"}).mock(
        return_value=httpx.Response(200, json={"Items": [{"Id": "m1", "Name": "A Movie", "IsFolder": False}]})
    )
    plugin = make_plugin(host="jf.local", api_key="k1")

    summary = await plugin.get_summary()

    assert summary["connected"] is True
    assert summary["recent_items"][0]["id"] == "m1"


@respx.mock
async def test_get_summary_degrades_gracefully_on_connection_error():
    respx.get("http://jf.local:8096/Items", params={"Recursive": "true"}).mock(return_value=httpx.Response(500))
    plugin = make_plugin(host="jf.local", api_key="k1")

    summary = await plugin.get_summary()

    assert summary["connected"] is True
    assert summary["recent_items"] == []


async def test_default_playback_mode_is_compatible():
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["playback_mode"] == "compatible"
