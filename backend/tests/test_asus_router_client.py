from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

from app.integrations import asus_router_client
from app.storage.cache import cache

SETTINGS = {"host": "router.local", "port": 443, "use_https": True, "username": "admin", "password": "secret"}
SETTINGS_HTTP = {"host": "192.168.50.1", "port": 80, "use_https": False, "username": "admin", "password": "secret"}
SETTINGS_NONDEFAULT_PORT = {
    "host": "router.local",
    "port": 8443,
    "use_https": True,
    "username": "admin",
    "password": "secret",
}


def test_is_configured_true_when_host_and_username_set():
    assert asus_router_client.is_configured(SETTINGS)


def test_is_configured_false_without_username():
    assert not asus_router_client.is_configured({"host": "router.local"})


def test_is_configured_false_without_password():
    assert not asus_router_client.is_configured({"host": "router.local", "username": "admin"})


@respx.mock
async def test_authenticate_caches_session_from_cookie():
    route = respx.post("https://router.local:443/login.cgi").mock(
        return_value=httpx.Response(200, headers={"set-cookie": "asus_token=tok1; Path=/"})
    )

    session = await asus_router_client._resolve_session(SETTINGS, "r1")

    assert route.called
    assert session.token == "tok1"
    assert cache.get("asus_token:r1").token == "tok1"


@respx.mock
async def test_authenticate_falls_back_to_json_body_token():
    respx.post("https://router.local:443/login.cgi").mock(return_value=httpx.Response(200, json={"asus_token": "tok2"}))

    session = await asus_router_client._resolve_session(SETTINGS, "r2")

    assert session.token == "tok2"


@respx.mock
async def test_resolve_session_reuses_cached_session():
    route = respx.post("https://router.local:443/login.cgi").mock(
        return_value=httpx.Response(200, json={"asus_token": "tok3"})
    )

    await asus_router_client._resolve_session(SETTINGS, "r3")
    await asus_router_client._resolve_session(SETTINGS, "r3")

    assert route.call_count == 1


@respx.mock
async def test_resolve_session_serializes_concurrent_cold_cache_calls():
    # AsusWRT/Merlin only tracks one active session at a time, so two
    # concurrent logins from our own process would invalidate each other's
    # token on the router. On a cold cache, concurrent resolvers must
    # serialize down to a single login.cgi call instead of racing.
    route = respx.post("https://router.local:443/login.cgi").mock(
        return_value=httpx.Response(200, json={"asus_token": "tok-concurrent"})
    )

    results = await asyncio.gather(
        asus_router_client._resolve_session(SETTINGS, "r33-concurrent"),
        asus_router_client._resolve_session(SETTINGS, "r33-concurrent"),
        asus_router_client._resolve_session(SETTINGS, "r33-concurrent"),
    )

    assert route.call_count == 1
    assert {session.token for session in results} == {"tok-concurrent"}


@respx.mock
async def test_authenticate_rejects_missing_token():
    respx.post("https://router.local:443/login.cgi").mock(return_value=httpx.Response(200, json={}))

    with pytest.raises(asus_router_client.AsusRouterError):
        await asus_router_client._resolve_session(SETTINGS, "r4")


@respx.mock
async def test_authenticate_raises_on_http_error_status():
    respx.post("https://router.local:443/login.cgi").mock(return_value=httpx.Response(500))

    with pytest.raises(asus_router_client.AsusRouterError):
        await asus_router_client._resolve_session(SETTINGS, "r5")


@respx.mock
async def test_authenticate_over_plain_http():
    route = respx.post("http://192.168.50.1:80/login.cgi").mock(
        return_value=httpx.Response(200, json={"asus_token": "tok-http"})
    )

    session = await asus_router_client._resolve_session(SETTINGS_HTTP, "r12")

    assert route.called
    assert session.token == "tok-http"


@respx.mock
async def test_authenticate_follows_redirect_and_keeps_cookie():
    respx.post("https://router.local:443/login.cgi").mock(
        return_value=httpx.Response(
            302,
            headers={"set-cookie": "asus_token=tok-redirect; Path=/", "location": "/index.asp"},
        )
    )
    respx.get("https://router.local:443/index.asp").mock(return_value=httpx.Response(200, html="<html></html>"))

    session = await asus_router_client._resolve_session(SETTINGS, "r13")

    assert session.token == "tok-redirect"


@respx.mock
async def test_authenticate_reports_login_page_returned():
    respx.post("https://router.local:443/login.cgi").mock(
        return_value=httpx.Response(200, html="<html>login form</html>")
    )

    with pytest.raises(asus_router_client.AsusRouterError, match="login page"):
        await asus_router_client._resolve_session(SETTINGS, "r14")


@respx.mock
async def test_authenticate_reports_login_page_returned_includes_title():
    respx.post("https://router.local:443/login.cgi").mock(
        return_value=httpx.Response(200, html="<html><head><title>ASUS Login</title></head></html>")
    )

    with pytest.raises(asus_router_client.AsusRouterError, match="ASUS Login"):
        await asus_router_client._resolve_session(SETTINGS, "r16")


@respx.mock
async def test_authenticate_sends_login_form_fields_matching_real_browser():
    route = respx.post("https://router.local:443/login.cgi").mock(
        return_value=httpx.Response(200, json={"asus_token": "tok"})
    )

    await asus_router_client._resolve_session(SETTINGS, "r17")

    sent = dict(httpx.QueryParams(route.calls.last.request.content.decode()))
    assert sent["current_page"] == "Main_Login.asp"
    # Captured from a live browser trace: the firmware rejects the login
    # (re-serves the login page) unless these are empty, not populated with
    # plausible-looking values.
    assert sent["action_mode"] == ""
    assert sent["next_page"] == ""
    assert sent["login_captcha"] == ""
    assert "login_authorization" in sent

    # Default port (443 for https) must be omitted from Origin/Referer,
    # matching what a real browser sends — some firmware CSRF-checks these
    # against the LAN host with a literal string/prefix match.
    request_headers = route.calls.last.request.headers
    assert request_headers["referer"] == "https://router.local/Main_Login.asp"
    assert request_headers["origin"] == "https://router.local"


@respx.mock
async def test_authenticate_keeps_non_default_port_in_origin_and_referer():
    route = respx.post("https://router.local:8443/login.cgi").mock(
        return_value=httpx.Response(200, json={"asus_token": "tok"})
    )

    await asus_router_client._resolve_session(SETTINGS_NONDEFAULT_PORT, "r18")

    request_headers = route.calls.last.request.headers
    assert request_headers["referer"] == "https://router.local:8443/Main_Login.asp"
    assert request_headers["origin"] == "https://router.local:8443"


@respx.mock
async def test_authenticate_omits_default_port_when_port_is_a_string():
    # Settings can round-trip through JSON storage that doesn't guarantee
    # `port` stays a native int — a stringified "443" must still be treated
    # as the default and omitted from Origin/Referer (see _base_url).
    settings = {**SETTINGS, "port": "443"}
    route = respx.post("https://router.local/login.cgi").mock(
        return_value=httpx.Response(200, json={"asus_token": "tok"})
    )

    await asus_router_client._resolve_session(settings, "r30")

    request_headers = route.calls.last.request.headers
    assert request_headers["referer"] == "https://router.local/Main_Login.asp"
    assert request_headers["origin"] == "https://router.local"


@respx.mock
async def test_authenticate_omits_default_port_when_port_is_none():
    settings = {**SETTINGS, "port": None}
    route = respx.post("https://router.local/login.cgi").mock(
        return_value=httpx.Response(200, json={"asus_token": "tok"})
    )

    await asus_router_client._resolve_session(settings, "r31")

    request_headers = route.calls.last.request.headers
    assert request_headers["referer"] == "https://router.local/Main_Login.asp"
    assert request_headers["origin"] == "https://router.local"


@respx.mock
async def test_authenticate_keeps_explicit_port_zero():
    # An explicit port of 0 must not be mistaken for "unset" and silently
    # swapped for the scheme default — falsy-coercion (`port or default`)
    # would do exactly that, since 0 is falsy.
    settings = {**SETTINGS, "port": 0}
    route = respx.post("https://router.local:0/login.cgi").mock(
        return_value=httpx.Response(200, json={"asus_token": "tok"})
    )

    await asus_router_client._resolve_session(settings, "r34")

    request_headers = route.calls.last.request.headers
    assert request_headers["referer"] == "https://router.local:0/Main_Login.asp"
    assert request_headers["origin"] == "https://router.local:0"


@respx.mock
async def test_authenticate_treats_string_use_https_false_as_http():
    settings = {**SETTINGS_HTTP, "use_https": "false"}
    route = respx.post("http://192.168.50.1/login.cgi").mock(
        return_value=httpx.Response(200, json={"asus_token": "tok"})
    )

    await asus_router_client._resolve_session(settings, "r32")

    request_headers = route.calls.last.request.headers
    assert request_headers["referer"] == "http://192.168.50.1/Main_Login.asp"
    assert request_headers["origin"] == "http://192.168.50.1"


@respx.mock
async def test_authenticate_reports_error_status_lockout():
    respx.post("https://router.local:443/login.cgi").mock(return_value=httpx.Response(200, json={"error_status": "3"}))

    with pytest.raises(asus_router_client.AsusRouterError, match="error_status 3"):
        await asus_router_client._resolve_session(SETTINGS, "r15")


@respx.mock
async def test_test_connection_returns_product_id():
    respx.post("https://router.local:443/login.cgi").mock(return_value=httpx.Response(200, json={"asus_token": "tok"}))
    respx.post("https://router.local:443/appGet.cgi").mock(
        return_value=httpx.Response(200, json={"productid": "RT-AX88U"})
    )

    product_id = await asus_router_client.test_connection(SETTINGS, "r6")

    assert product_id == "RT-AX88U"


@respx.mock
async def test_hook_retries_once_on_401():
    auth_route = respx.post("https://router.local:443/login.cgi").mock(
        side_effect=[
            httpx.Response(200, json={"asus_token": "stale"}),
            httpx.Response(200, json={"asus_token": "fresh"}),
        ]
    )
    hook_route = respx.post("https://router.local:443/appGet.cgi").mock(
        side_effect=[
            httpx.Response(401),
            httpx.Response(200, json={"productid": "RT-AX88U"}),
        ]
    )

    product_id = await asus_router_client.test_connection(SETTINGS, "r7")

    assert product_id == "RT-AX88U"
    assert auth_route.call_count == 2
    assert hook_route.call_count == 2


@respx.mock
async def test_hook_raises_after_retry_still_fails():
    respx.post("https://router.local:443/login.cgi").mock(return_value=httpx.Response(200, json={"asus_token": "tok"}))
    respx.post("https://router.local:443/appGet.cgi").mock(return_value=httpx.Response(403))

    with pytest.raises(asus_router_client.AsusRouterError):
        await asus_router_client.test_connection(SETTINGS, "r8")


@respx.mock
async def test_hook_reports_login_page_bounce_without_retrying():
    # A 200 with HTML back from the hook endpoint (not 401/403) means the
    # router accepted the session token but is bouncing every request back
    # to Main_Login.asp anyway — Merlin firmware does this when it's
    # requiring a captcha or has rate-limited logins after repeated failed
    # attempts. This must not trigger the 401/403 re-auth-and-retry path:
    # retrying a login here only makes an active lockout worse.
    auth_route = respx.post("https://router.local:443/login.cgi").mock(
        return_value=httpx.Response(200, json={"asus_token": "tok"})
    )
    hook_route = respx.post("https://router.local:443/appGet.cgi").mock(
        return_value=httpx.Response(
            200, html="<html><script>window.top.location.href='/Main_Login.asp';</script></html>"
        )
    )

    with pytest.raises(asus_router_client.AsusRouterError, match="requiring a captcha"):
        await asus_router_client.test_connection(SETTINGS, "r33")

    assert auth_route.call_count == 1
    assert hook_route.call_count == 1


@respx.mock
async def test_get_clients_maps_fields():
    respx.post("https://router.local:443/login.cgi").mock(return_value=httpx.Response(200, json={"asus_token": "tok"}))
    respx.post("https://router.local:443/appGet.cgi").mock(
        return_value=httpx.Response(
            200,
            json={
                "get_clientlist": {
                    "AA:BB:CC:DD:EE:FF": {"nickName": "Laptop", "ip": "192.168.1.10", "isOnline": "1"},
                    "11:22:33:44:55:66": {"name": "Phone", "ip": "192.168.1.11", "isOnline": "0"},
                    "maclist": ["AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"],
                }
            },
        )
    )

    clients = await asus_router_client.get_clients(SETTINGS, "r9")

    assert {"name": "Laptop", "ip": "192.168.1.10", "online": True} in clients
    assert {"name": "Phone", "ip": "192.168.1.11", "online": False} in clients
    assert len(clients) == 2


@respx.mock
async def test_get_wan_status_maps_fields():
    respx.post("https://router.local:443/login.cgi").mock(return_value=httpx.Response(200, json={"asus_token": "tok"}))
    respx.post("https://router.local:443/appGet.cgi").mock(
        return_value=httpx.Response(200, json={"wanlink_statusstr": "Connected", "wanlink_ipaddr": "203.0.113.5"})
    )

    status = await asus_router_client.get_wan_status(SETTINGS, "r10")

    assert status == {"connected": True, "ip": "203.0.113.5"}


@respx.mock
async def test_get_wan_status_disconnected_when_statusstr_not_connected():
    respx.post("https://router.local:443/login.cgi").mock(return_value=httpx.Response(200, json={"asus_token": "tok"}))
    respx.post("https://router.local:443/appGet.cgi").mock(
        return_value=httpx.Response(
            200, json={"wanlink_status": 2, "wanlink_statusstr": "Disconnected", "wanlink_ipaddr": None}
        )
    )

    status = await asus_router_client.get_wan_status(SETTINGS, "r19")

    # wanlink_status's numeric convention isn't trusted anymore — only the
    # status string is, since a real router was observed reporting status 1
    # while its own statusstr said "Connected", contradicting the old == 2
    # assumption.
    assert status == {"connected": False, "ip": None}


@respx.mock
async def test_hook_parses_js_function_literal_response():
    respx.post("https://router.local:443/login.cgi").mock(return_value=httpx.Response(200, json={"asus_token": "tok"}))
    js_body = (
        '{\n"wanlink":function wanlink_status() { return 1;}\n'
        "function wanlink_statusstr() { return 'Connected';}\n"
        "function wanlink_type() { return 'dhcp';}\n"
        "function wanlink_ipaddr() { return '71.35.0.81';}\n"
        "function wanlink_netmask() { return '255.255.224.0';}\n"
        "function wanlink_gateway() { return '71.35.0.1';}\n"
    )
    respx.post("https://router.local:443/appGet.cgi").mock(
        return_value=httpx.Response(200, content=js_body, headers={"content-type": "text/html"})
    )

    status = await asus_router_client.get_wan_status(SETTINGS, "r20")

    assert status == {"connected": True, "ip": "71.35.0.81"}


@respx.mock
async def test_get_traffic_maps_fields():
    respx.post("https://router.local:443/login.cgi").mock(return_value=httpx.Response(200, json={"asus_token": "tok"}))
    respx.post("https://router.local:443/appGet.cgi").mock(
        return_value=httpx.Response(200, json={"netdev": {"INTERNET_rx": "1024", "INTERNET_tx": "512"}})
    )

    traffic = await asus_router_client.get_traffic(SETTINGS, "r11")

    assert traffic == {"rx_bytes": 1024, "tx_bytes": 512}


@respx.mock
async def test_get_traffic_parses_js_object_literal_response():
    respx.post("https://router.local:443/login.cgi").mock(return_value=httpx.Response(200, json={"asus_token": "tok"}))
    js_body = (
        '{\n"netdev":{\nnetdev = {\n'
        " 'BRIDGE':{rx:0xc1ea8ae3a,tx:0x3f60851e09}\n"
        ",'INTERNET':{rx:0x3fb206ad05,tx:0xc170ee181}\n"
        ",'WIRED':{rx:0x1eda6f1ba7,tx:0x466a77106f}\n"
        "}}\n}\n"
    )
    respx.post("https://router.local:443/appGet.cgi").mock(
        return_value=httpx.Response(200, content=js_body, headers={"content-type": "text/html"})
    )

    traffic = await asus_router_client.get_traffic(SETTINGS, "r21")

    assert traffic == {"rx_bytes": 0x3FB206AD05, "tx_bytes": 0xC170EE181}
