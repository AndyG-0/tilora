from __future__ import annotations

import httpx
import pytest
import respx

from app.integrations import qbittorrent_client
from app.storage.cache import cache

SETTINGS = {"host": "qbit.local", "port": 8080, "use_https": False, "username": "admin", "password": "secret"}


def _login_response(sid: str = "sid1") -> httpx.Response:
    return httpx.Response(200, text="Ok.", headers={"Set-Cookie": f"SID={sid}; Path=/"})


def test_is_configured_true_when_host_set():
    assert qbittorrent_client.is_configured(SETTINGS)


def test_is_configured_false_without_host():
    assert not qbittorrent_client.is_configured({"password": "secret"})


@respx.mock
async def test_authenticate_caches_session():
    route = respx.post("http://qbit.local:8080/api/v2/auth/login").mock(return_value=_login_response())

    session = await qbittorrent_client._resolve_session(SETTINGS, "w1")

    assert route.called
    assert session.sid == "sid1"
    assert cache.get("qbittorrent_sid:w1").sid == "sid1"


@respx.mock
async def test_resolve_session_reuses_cached_session():
    route = respx.post("http://qbit.local:8080/api/v2/auth/login").mock(return_value=_login_response())

    await qbittorrent_client._resolve_session(SETTINGS, "w2")
    await qbittorrent_client._resolve_session(SETTINGS, "w2")

    assert route.call_count == 1


@respx.mock
async def test_authenticate_rejects_bad_credentials():
    respx.post("http://qbit.local:8080/api/v2/auth/login").mock(return_value=httpx.Response(200, text="Fails."))

    with pytest.raises(qbittorrent_client.QBittorrentError):
        await qbittorrent_client._resolve_session(SETTINGS, "w3")


@respx.mock
async def test_authenticate_raises_on_ip_ban():
    respx.post("http://qbit.local:8080/api/v2/auth/login").mock(return_value=httpx.Response(403))

    with pytest.raises(qbittorrent_client.QBittorrentError, match="banned"):
        await qbittorrent_client._resolve_session(SETTINGS, "w4")


@respx.mock
async def test_test_connection_returns_version():
    respx.post("http://qbit.local:8080/api/v2/auth/login").mock(return_value=_login_response())
    respx.get("http://qbit.local:8080/api/v2/app/version").mock(return_value=httpx.Response(200, text="v4.6.0"))

    version = await qbittorrent_client.test_connection(SETTINGS, "w5")

    assert version == "4.6.0"


@respx.mock
async def test_request_sends_sid_cookie():
    respx.post("http://qbit.local:8080/api/v2/auth/login").mock(return_value=_login_response())
    route = respx.get("http://qbit.local:8080/api/v2/sync/maindata").mock(
        return_value=httpx.Response(200, json={"torrents": {}, "server_state": {}})
    )

    await qbittorrent_client.get_maindata(SETTINGS, "w6")

    assert route.calls.last.request.headers["cookie"] == "SID=sid1"


@respx.mock
async def test_request_retries_once_on_403():
    auth_route = respx.post("http://qbit.local:8080/api/v2/auth/login").mock(
        side_effect=[_login_response("stale"), _login_response("fresh")]
    )
    version_route = respx.get("http://qbit.local:8080/api/v2/app/version").mock(
        side_effect=[httpx.Response(403), httpx.Response(200, text="v4.6.0")]
    )

    version = await qbittorrent_client.test_connection(SETTINGS, "w7")

    assert version == "4.6.0"
    assert auth_route.call_count == 2
    assert version_route.call_count == 2


@respx.mock
async def test_get_maindata_returns_raw_payload():
    respx.post("http://qbit.local:8080/api/v2/auth/login").mock(return_value=_login_response())
    respx.get("http://qbit.local:8080/api/v2/sync/maindata").mock(
        return_value=httpx.Response(200, json={"torrents": {"h1": {"name": "x"}}, "server_state": {"dl_info_speed": 1}})
    )

    data = await qbittorrent_client.get_maindata(SETTINGS, "w8")

    assert data["torrents"]["h1"]["name"] == "x"
    assert data["server_state"]["dl_info_speed"] == 1


@respx.mock
async def test_request_raises_qbittorrent_error_on_server_error():
    respx.post("http://qbit.local:8080/api/v2/auth/login").mock(return_value=_login_response())
    respx.get("http://qbit.local:8080/api/v2/sync/maindata").mock(return_value=httpx.Response(500))

    with pytest.raises(qbittorrent_client.QBittorrentError):
        await qbittorrent_client.get_maindata(SETTINGS, "w9")
