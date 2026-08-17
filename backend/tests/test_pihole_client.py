from __future__ import annotations

import json

import httpx
import pytest
import respx

from app.integrations import pihole_client
from app.storage.cache import cache

SETTINGS = {"host": "pi.local", "port": 80, "use_https": False, "password": "secret"}

AUTH_OK = {"session": {"valid": True, "sid": "sid1", "csrf": "csrf1", "validity": 1800}}


def test_is_configured_true_when_host_set():
    assert pihole_client.is_configured(SETTINGS)


def test_is_configured_false_without_host():
    assert not pihole_client.is_configured({"password": "secret"})


@respx.mock
async def test_authenticate_caches_session():
    route = respx.post("http://pi.local:80/api/auth").mock(return_value=httpx.Response(200, json=AUTH_OK))

    session = await pihole_client._resolve_session(SETTINGS, "w1")

    assert route.called
    assert session.sid == "sid1"
    assert session.csrf == "csrf1"
    assert cache.get("pihole_sid:w1").sid == "sid1"


@respx.mock
async def test_resolve_session_reuses_cached_session():
    route = respx.post("http://pi.local:80/api/auth").mock(return_value=httpx.Response(200, json=AUTH_OK))

    await pihole_client._resolve_session(SETTINGS, "w2")
    await pihole_client._resolve_session(SETTINGS, "w2")

    assert route.call_count == 1


@respx.mock
async def test_authenticate_rejects_bad_password():
    respx.post("http://pi.local:80/api/auth").mock(return_value=httpx.Response(401))

    with pytest.raises(pihole_client.PiholeError):
        await pihole_client._resolve_session(SETTINGS, "w3")


@respx.mock
async def test_authenticate_raises_when_session_invalid():
    respx.post("http://pi.local:80/api/auth").mock(
        return_value=httpx.Response(200, json={"session": {"valid": False, "message": "password incorrect"}})
    )

    with pytest.raises(pihole_client.PiholeError, match="password incorrect"):
        await pihole_client._resolve_session(SETTINGS, "w4")


@respx.mock
async def test_test_connection_returns_core_version():
    respx.post("http://pi.local:80/api/auth").mock(return_value=httpx.Response(200, json=AUTH_OK))
    respx.get("http://pi.local:80/api/info/version").mock(
        return_value=httpx.Response(200, json={"version": {"core": {"local": {"version": "v6.0.1"}}}})
    )

    version = await pihole_client.test_connection(SETTINGS, "w5")

    assert version == "v6.0.1"


@respx.mock
async def test_request_sends_sid_and_csrf():
    respx.post("http://pi.local:80/api/auth").mock(return_value=httpx.Response(200, json=AUTH_OK))
    route = respx.post("http://pi.local:80/api/dns/blocking").mock(
        return_value=httpx.Response(200, json={"blocking": "disabled", "timer": None})
    )

    await pihole_client.set_blocking(SETTINGS, "w6", False)

    request = route.calls.last.request
    assert dict(httpx.QueryParams(request.url.query))["sid"] == "sid1"
    assert request.headers["X-FTL-SID"] == "sid1"
    assert request.headers["sid"] == "sid1"
    assert request.headers["X-FTL-CSRF"] == "csrf1"


@respx.mock
async def test_request_retries_once_on_401():
    auth_route = respx.post("http://pi.local:80/api/auth").mock(
        side_effect=[
            httpx.Response(200, json={"session": {"valid": True, "sid": "stale", "csrf": "c1", "validity": 1800}}),
            httpx.Response(200, json={"session": {"valid": True, "sid": "fresh", "csrf": "c2", "validity": 1800}}),
        ]
    )
    info_route = respx.get("http://pi.local:80/api/info/version").mock(
        side_effect=[
            httpx.Response(401),
            httpx.Response(200, json={"version": {"core": {"local": {"version": "v6.0.1"}}}}),
        ]
    )

    version = await pihole_client.test_connection(SETTINGS, "w7")

    assert version == "v6.0.1"
    assert auth_route.call_count == 2
    assert info_route.call_count == 2


@respx.mock
async def test_get_summary_stats_returns_raw_payload():
    respx.post("http://pi.local:80/api/auth").mock(return_value=httpx.Response(200, json=AUTH_OK))
    get_route = respx.get("http://pi.local:80/api/stats/summary").mock(
        return_value=httpx.Response(
            200,
            json={
                "queries": {"total": 100, "blocked": 20, "percent_blocked": 20.0},
                "clients": {"active": 3, "total": 5},
                "gravity": {"domains_being_blocked": 1000000, "last_update": 123},
            },
        )
    )

    stats = await pihole_client.get_summary_stats(SETTINGS, "w8")

    assert stats["queries"]["total"] == 100
    assert stats["clients"]["active"] == 3
    assert stats["gravity"]["domains_being_blocked"] == 1000000
    req = get_route.calls.last.request
    assert req.headers["X-FTL-SID"] == "sid1"
    assert req.headers["sid"] == "sid1"
    assert req.headers["X-FTL-CSRF"] == "csrf1"


@respx.mock
async def test_get_top_domains_maps_fields():
    respx.post("http://pi.local:80/api/auth").mock(return_value=httpx.Response(200, json=AUTH_OK))
    route = respx.get("http://pi.local:80/api/stats/top_domains").mock(
        return_value=httpx.Response(
            200, json={"domains": [{"domain": "ads.example.com", "count": 42}], "total_queries": 100}
        )
    )

    domains = await pihole_client.get_top_domains(SETTINGS, "w9", blocked=True, count=5)

    assert domains == [{"domain": "ads.example.com", "count": 42}]
    params = dict(httpx.QueryParams(route.calls.last.request.url.query))
    assert params["blocked"] == "true"
    assert params["count"] == "5"


@respx.mock
async def test_get_blocking_status():
    respx.post("http://pi.local:80/api/auth").mock(return_value=httpx.Response(200, json=AUTH_OK))
    respx.get("http://pi.local:80/api/dns/blocking").mock(
        return_value=httpx.Response(200, json={"blocking": "enabled", "timer": None})
    )

    status = await pihole_client.get_blocking_status(SETTINGS, "w10")

    assert status == {"blocking": "enabled", "timer": None}


@respx.mock
async def test_set_blocking_sends_payload():
    respx.post("http://pi.local:80/api/auth").mock(return_value=httpx.Response(200, json=AUTH_OK))
    route = respx.post("http://pi.local:80/api/dns/blocking").mock(
        return_value=httpx.Response(200, json={"blocking": "disabled", "timer": 300})
    )

    result = await pihole_client.set_blocking(SETTINGS, "w11", False, timer=300)

    assert result == {"blocking": "disabled", "timer": 300}
    assert json.loads(route.calls.last.request.content) == {"blocking": False, "timer": 300}


@respx.mock
async def test_request_raises_pihole_error_on_server_error():
    respx.post("http://pi.local:80/api/auth").mock(return_value=httpx.Response(200, json=AUTH_OK))
    respx.get("http://pi.local:80/api/stats/summary").mock(return_value=httpx.Response(500))

    with pytest.raises(pihole_client.PiholeError):
        await pihole_client.get_summary_stats(SETTINGS, "w12")
