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
    assert summary["sections"] == []


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
    assert len(summary["sections"]) == 1
    assert summary["sections"][0]["label"] == "Recently added"
    assert summary["sections"][0]["items"][0]["id"] == "m1"


@respx.mock
async def test_get_summary_degrades_gracefully_on_connection_error():
    respx.get("http://jf.local:8096/Items", params={"Recursive": "true"}).mock(return_value=httpx.Response(500))
    plugin = make_plugin(host="jf.local", api_key="k1")

    summary = await plugin.get_summary()

    assert summary["connected"] is True
    assert summary["sections"] == [{"label": "Recently added", "items": []}]


async def test_default_playback_mode_is_compatible():
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["playback_mode"] == "compatible"


async def test_default_content_mode_is_added():
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["content_mode"] == "added"


async def test_resume_available_reflects_auth_mode():
    api_key_plugin = make_plugin(auth_mode="api_key")
    password_plugin = make_plugin(auth_mode="password")

    assert (await api_key_plugin.get_detail())["resume_available"] is False
    assert (await password_plugin.get_detail())["resume_available"] is True


@respx.mock
async def test_get_summary_played_mode_uses_resume_items():
    respx.post("http://jf.local:8096/Users/AuthenticateByName").mock(
        return_value=httpx.Response(200, json={"AccessToken": "tok1", "User": {"Id": "u1"}})
    )
    respx.get("http://jf.local:8096/Users/u1/Items/Resume").mock(
        return_value=httpx.Response(200, json={"Items": [{"Id": "m2", "Name": "Half-watched", "IsFolder": False}]})
    )
    plugin = make_plugin(host="jf.local", auth_mode="password", username="u", password="p", content_mode="played")

    summary = await plugin.get_summary()

    assert len(summary["sections"]) == 1
    assert summary["sections"][0]["label"] == "Continue watching"
    assert summary["sections"][0]["items"][0]["id"] == "m2"


@respx.mock
async def test_get_summary_both_mode_includes_both_sections_in_order():
    respx.post("http://jf.local:8096/Users/AuthenticateByName").mock(
        return_value=httpx.Response(200, json={"AccessToken": "tok1", "User": {"Id": "u1"}})
    )
    respx.get("http://jf.local:8096/Users/u1/Items", params={"Recursive": "true"}).mock(
        return_value=httpx.Response(200, json={"Items": [{"Id": "m1", "Name": "A Movie", "IsFolder": False}]})
    )
    respx.get("http://jf.local:8096/Users/u1/Items/Resume").mock(
        return_value=httpx.Response(200, json={"Items": [{"Id": "m2", "Name": "Half-watched", "IsFolder": False}]})
    )
    plugin = make_plugin(host="jf.local", auth_mode="password", username="u", password="p", content_mode="both")

    summary = await plugin.get_summary()

    assert [section["label"] for section in summary["sections"]] == ["Recently added", "Continue watching"]
    assert summary["sections"][0]["items"][0]["id"] == "m1"
    assert summary["sections"][1]["items"][0]["id"] == "m2"


@respx.mock
async def test_get_summary_played_mode_with_api_key_auth_returns_empty_section():
    plugin = make_plugin(host="jf.local", api_key="k1", content_mode="played")

    summary = await plugin.get_summary()

    assert summary["sections"] == [{"label": "Continue watching", "items": []}]
