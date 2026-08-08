from __future__ import annotations

import json

import httpx
import pytest
import respx

from app.integrations import track17_client

API_KEY = "test-key"


def test_is_configured_true_when_key_set():
    assert track17_client.is_configured({"track17_api_key": API_KEY})


def test_is_configured_false_without_key():
    assert not track17_client.is_configured({})


@respx.mock
async def test_register_sends_the_token_header_and_tracking_number():
    route = respx.post("https://api.17track.net/track/v2.2/register").mock(
        return_value=httpx.Response(200, json={"code": 0, "data": {"accepted": [{"number": "1Z999AA1"}]}})
    )

    await track17_client.register(API_KEY, "1Z999AA1")

    assert route.called
    request = route.calls.last.request
    assert request.headers["17token"] == API_KEY
    assert json.loads(request.content) == [{"number": "1Z999AA1"}]


@respx.mock
async def test_register_raises_on_error_code():
    respx.post("https://api.17track.net/track/v2.2/register").mock(
        return_value=httpx.Response(200, json={"code": -1, "message": "invalid number"})
    )

    with pytest.raises(track17_client.Track17Error, match="invalid number"):
        await track17_client.register(API_KEY, "bad-number")


@respx.mock
async def test_register_raises_on_http_error():
    respx.post("https://api.17track.net/track/v2.2/register").mock(return_value=httpx.Response(500))

    with pytest.raises(track17_client.Track17Error):
        await track17_client.register(API_KEY, "1Z999AA1")


@respx.mock
async def test_get_track_info_parses_carrier_status_event_and_eta():
    respx.post("https://api.17track.net/track/v2.2/gettrackinfo").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "accepted": [
                        {
                            "number": "1Z999AA1",
                            "carrier": 100002,
                            "track_info": {
                                "latest_status": {"status": "InTransit"},
                                "latest_event": {
                                    "description": "Departed facility",
                                    "time_iso": "2026-08-05T10:00:00Z",
                                },
                                "time_metrics": {"estimated_delivery_date": {"from": "2026-08-07", "to": "2026-08-08"}},
                            },
                        }
                    ],
                    "rejected": [],
                },
            },
        )
    )

    results = await track17_client.get_track_info(API_KEY, ["1Z999AA1"])

    assert results["1Z999AA1"] == {
        "tracking_number": "1Z999AA1",
        "carrier": "100002",
        "status": "InTransit",
        "last_event": "Departed facility",
        "eta_date": "2026-08-08",
        "delivered": False,
    }


@respx.mock
async def test_get_track_info_flags_delivered_status():
    respx.post("https://api.17track.net/track/v2.2/gettrackinfo").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "accepted": [
                        {
                            "number": "1Z999AA1",
                            "carrier": 100002,
                            "track_info": {"latest_status": {"status": "Delivered"}},
                        }
                    ]
                },
            },
        )
    )

    results = await track17_client.get_track_info(API_KEY, ["1Z999AA1"])

    assert results["1Z999AA1"]["delivered"] is True


@respx.mock
async def test_get_track_info_omits_rejected_numbers():
    respx.post("https://api.17track.net/track/v2.2/gettrackinfo").mock(
        return_value=httpx.Response(200, json={"code": 0, "data": {"accepted": [], "rejected": [{"number": "bad"}]}})
    )

    results = await track17_client.get_track_info(API_KEY, ["bad"])

    assert results == {}


@respx.mock
async def test_get_track_info_tolerates_missing_nested_fields():
    respx.post("https://api.17track.net/track/v2.2/gettrackinfo").mock(
        return_value=httpx.Response(200, json={"code": 0, "data": {"accepted": [{"number": "1Z999AA1"}]}})
    )

    results = await track17_client.get_track_info(API_KEY, ["1Z999AA1"])

    assert results["1Z999AA1"] == {
        "tracking_number": "1Z999AA1",
        "carrier": None,
        "status": None,
        "last_event": None,
        "eta_date": None,
        "delivered": False,
    }


async def test_get_track_info_returns_empty_dict_for_no_numbers():
    assert await track17_client.get_track_info(API_KEY, []) == {}


@respx.mock
async def test_get_track_info_raises_on_http_error():
    respx.post("https://api.17track.net/track/v2.2/gettrackinfo").mock(return_value=httpx.Response(500))

    with pytest.raises(track17_client.Track17Error):
        await track17_client.get_track_info(API_KEY, ["1Z999AA1"])
