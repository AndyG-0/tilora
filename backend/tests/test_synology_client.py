from __future__ import annotations

import httpx
import pytest
import respx

from app.integrations import synology_client
from app.storage.cache import cache

SETTINGS = {"host": "syno.local", "port": 5000, "use_https": False, "username": "admin", "password": "secret"}

AUTH_OK = {"success": True, "data": {"sid": "sid1"}}


def test_is_configured_true_when_host_and_username_set():
    assert synology_client.is_configured(SETTINGS)


def test_is_configured_false_without_username():
    assert not synology_client.is_configured({"host": "syno.local"})


def test_is_configured_false_without_password():
    assert not synology_client.is_configured({"host": "syno.local", "username": "admin"})


@respx.mock
async def test_authenticate_caches_session():
    route = respx.get("http://syno.local:5000/webapi/auth.cgi").mock(return_value=httpx.Response(200, json=AUTH_OK))

    session = await synology_client._resolve_session(SETTINGS, "s1")

    assert route.called
    assert session.sid == "sid1"
    assert cache.get("synology_sid:s1").sid == "sid1"


@respx.mock
async def test_resolve_session_reuses_cached_session():
    route = respx.get("http://syno.local:5000/webapi/auth.cgi").mock(return_value=httpx.Response(200, json=AUTH_OK))

    await synology_client._resolve_session(SETTINGS, "s2")
    await synology_client._resolve_session(SETTINGS, "s2")

    assert route.call_count == 1


@respx.mock
async def test_authenticate_rejects_bad_credentials():
    respx.get("http://syno.local:5000/webapi/auth.cgi").mock(
        return_value=httpx.Response(200, json={"success": False, "error": {"code": 400}})
    )

    with pytest.raises(synology_client.SynologyError, match="incorrect"):
        await synology_client._resolve_session(SETTINGS, "s3")


@respx.mock
async def test_authenticate_surfaces_permission_denied_code():
    respx.get("http://syno.local:5000/webapi/auth.cgi").mock(
        return_value=httpx.Response(200, json={"success": False, "error": {"code": 402}})
    )

    with pytest.raises(synology_client.SynologyError, match="permission denied"):
        await synology_client._resolve_session(SETTINGS, "s3b")


@respx.mock
async def test_authenticate_raises_on_http_error_status():
    respx.get("http://syno.local:5000/webapi/auth.cgi").mock(return_value=httpx.Response(500))

    with pytest.raises(synology_client.SynologyError):
        await synology_client._resolve_session(SETTINGS, "s4")


@respx.mock
async def test_test_connection_returns_model():
    respx.get("http://syno.local:5000/webapi/auth.cgi").mock(return_value=httpx.Response(200, json=AUTH_OK))
    respx.get("http://syno.local:5000/webapi/entry.cgi").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"model": "DS920+"}})
    )

    model = await synology_client.test_connection(SETTINGS, "s5")

    assert model == "DS920+"


@respx.mock
async def test_request_sends_sid_param():
    respx.get("http://syno.local:5000/webapi/auth.cgi").mock(return_value=httpx.Response(200, json=AUTH_OK))
    route = respx.get("http://syno.local:5000/webapi/entry.cgi").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"model": "DS920+"}})
    )

    await synology_client.test_connection(SETTINGS, "s6")

    params = dict(httpx.QueryParams(route.calls.last.request.url.query))
    assert params["_sid"] == "sid1"


@respx.mock
async def test_request_retries_once_on_unsuccessful_response():
    auth_route = respx.get("http://syno.local:5000/webapi/auth.cgi").mock(
        side_effect=[
            httpx.Response(200, json={"success": True, "data": {"sid": "stale"}}),
            httpx.Response(200, json={"success": True, "data": {"sid": "fresh"}}),
        ]
    )
    entry_route = respx.get("http://syno.local:5000/webapi/entry.cgi").mock(
        side_effect=[
            httpx.Response(200, json={"success": False, "error": {"code": 106}}),
            httpx.Response(200, json={"success": True, "data": {"model": "DS920+"}}),
        ]
    )

    model = await synology_client.test_connection(SETTINGS, "s7")

    assert model == "DS920+"
    assert auth_route.call_count == 2
    assert entry_route.call_count == 2


@respx.mock
async def test_request_raises_after_retry_still_fails():
    respx.get("http://syno.local:5000/webapi/auth.cgi").mock(return_value=httpx.Response(200, json=AUTH_OK))
    respx.get("http://syno.local:5000/webapi/entry.cgi").mock(
        return_value=httpx.Response(200, json={"success": False, "error": {"code": 106}})
    )

    with pytest.raises(synology_client.SynologyError, match="session timed out"):
        await synology_client.test_connection(SETTINGS, "s8")


@respx.mock
async def test_request_does_not_retry_on_permission_denied():
    auth_route = respx.get("http://syno.local:5000/webapi/auth.cgi").mock(
        return_value=httpx.Response(200, json=AUTH_OK)
    )
    entry_route = respx.get("http://syno.local:5000/webapi/entry.cgi").mock(
        return_value=httpx.Response(200, json={"success": False, "error": {"code": 105}})
    )

    with pytest.raises(synology_client.SynologyError, match="permission denied"):
        await synology_client.test_connection(SETTINGS, "s8b")

    assert auth_route.call_count == 1
    assert entry_route.call_count == 1


@respx.mock
async def test_get_storage_sends_load_info_method():
    respx.get("http://syno.local:5000/webapi/auth.cgi").mock(return_value=httpx.Response(200, json=AUTH_OK))
    route = respx.get("http://syno.local:5000/webapi/entry.cgi").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"volumes": []}})
    )

    await synology_client.get_storage(SETTINGS, "s14")

    params = dict(httpx.QueryParams(route.calls.last.request.url.query))
    assert params["method"] == "load_info"


@respx.mock
async def test_get_storage_maps_volume_fields():
    respx.get("http://syno.local:5000/webapi/auth.cgi").mock(return_value=httpx.Response(200, json=AUTH_OK))
    respx.get("http://syno.local:5000/webapi/entry.cgi").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "volumes": [
                        {
                            "id": "volume_1",
                            "desc": "Volume 1",
                            "status": "normal",
                            "size": {"total": "1000", "used": "250"},
                        }
                    ]
                },
            },
        )
    )

    volumes = await synology_client.get_storage(SETTINGS, "s9")

    assert volumes == [
        {
            "name": "Volume 1",
            "total_bytes": 1000,
            "used_bytes": 250,
            "used_percent": 25.0,
            "status": "normal",
        }
    ]


@respx.mock
async def test_get_storage_falls_back_to_id_when_no_desc():
    respx.get("http://syno.local:5000/webapi/auth.cgi").mock(return_value=httpx.Response(200, json=AUTH_OK))
    respx.get("http://syno.local:5000/webapi/entry.cgi").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "data": {"volumes": [{"id": "volume_1", "status": "normal", "size": {"total": "0", "used": "0"}}]},
            },
        )
    )

    volumes = await synology_client.get_storage(SETTINGS, "s10")

    assert volumes[0]["name"] == "volume_1"
    assert volumes[0]["used_percent"] == 0


@respx.mock
async def test_request_uses_discovered_max_version():
    respx.get("http://syno.local:5000/webapi/auth.cgi").mock(return_value=httpx.Response(200, json=AUTH_OK))
    respx.get("http://syno.local:5000/webapi/query.cgi").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "data": {"SYNO.Core.System": {"path": "entry.cgi", "minVersion": 1, "maxVersion": 3}},
            },
        )
    )
    entry_route = respx.get("http://syno.local:5000/webapi/entry.cgi").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"model": "DS920+"}})
    )

    await synology_client.test_connection(SETTINGS, "s12")

    params = dict(httpx.QueryParams(entry_route.calls.last.request.url.query))
    assert params["version"] == "3"


@respx.mock
async def test_request_falls_back_to_default_version_when_discovery_fails():
    respx.get("http://syno.local:5000/webapi/auth.cgi").mock(return_value=httpx.Response(200, json=AUTH_OK))
    respx.get("http://syno.local:5000/webapi/query.cgi").mock(return_value=httpx.Response(500))
    entry_route = respx.get("http://syno.local:5000/webapi/entry.cgi").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"model": "DS920+"}})
    )

    await synology_client.test_connection(SETTINGS, "s13")

    params = dict(httpx.QueryParams(entry_route.calls.last.request.url.query))
    assert params["version"] == "1"


@respx.mock
async def test_get_system_info_maps_fields():
    respx.get("http://syno.local:5000/webapi/auth.cgi").mock(return_value=httpx.Response(200, json=AUTH_OK))
    respx.get("http://syno.local:5000/webapi/entry.cgi").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "data": {"model": "DS920+", "up_time": "12:34:56", "temperature": 42},
            },
        )
    )

    info = await synology_client.get_system_info(SETTINGS, "s11")

    assert info == {"model": "DS920+", "uptime": "12:34:56", "temperature_celsius": 42}
