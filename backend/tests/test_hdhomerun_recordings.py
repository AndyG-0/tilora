from __future__ import annotations

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import hdhomerun
from app.auth import get_current_user
from app.integrations import hdhomerun_client
from app.storage.cache import cache

TUNER_SETTINGS = {"tuner_host": "hdhr.local", "tuner_port": 80, "dvr_host": "dvr.local", "dvr_port": 50000}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(hdhomerun.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "admin", "role": "admin"}
    return TestClient(app)


@respx.mock
@pytest.mark.asyncio
async def test_add_recording_rule_success():
    respx.get("http://hdhr.local:80/discover.json").mock(
        return_value=httpx.Response(200, json={"DeviceAuth": "test_auth_token"})
    )
    respx.post("https://api.hdhomerun.com/api/recording_rules").mock(
        return_value=httpx.Response(200, json=[{"RecordingRuleID": "123", "SeriesID": "S1001", "Title": "Test Show"}])
    )
    respx.get("http://dvr.local:50000/discover.json").mock(
        return_value=httpx.Response(200, json={"StorageURL": "http://dvr.local:50000/storage"})
    )
    respx.get("http://dvr.local:50000/storage").mock(return_value=httpx.Response(200, json=[]))

    rule_data = {"series_id": "S1001", "date_time": 1700000000, "channel": "4.1"}
    rules = await hdhomerun_client.add_recording_rule(TUNER_SETTINGS, rule_data)

    assert len(rules) == 1
    assert rules[0]["RecordingRuleID"] == "123"


@respx.mock
@pytest.mark.asyncio
async def test_delete_recording_rule_success():
    respx.get("http://hdhr.local:80/discover.json").mock(
        return_value=httpx.Response(200, json={"DeviceAuth": "test_auth_token"})
    )
    respx.post("https://api.hdhomerun.com/api/recording_rules").mock(return_value=httpx.Response(200, json=[]))
    respx.get("http://dvr.local:50000/discover.json").mock(return_value=httpx.Response(200, json={}))

    rules = await hdhomerun_client.delete_recording_rule(TUNER_SETTINGS, "123")
    assert rules == []


@respx.mock
@pytest.mark.asyncio
async def test_fetch_full_guide():
    cache.delete("hdhomerun_full_guide:hdhomerun")
    respx.get("http://hdhr.local:80/discover.json").mock(
        return_value=httpx.Response(200, json={"DeviceAuth": "test_auth_token"})
    )
    guide_route = respx.get("https://api.hdhomerun.com/api/guide.php")
    guide_route.side_effect = [
        httpx.Response(
            200,
            json=[
                {
                    "GuideNumber": "4.1",
                    "GuideName": "KDFW",
                    "Guide": [
                        {"SeriesID": "C101", "Title": "Morning News", "StartTime": 1700000000, "EndTime": 1700003600}
                    ],
                }
            ],
        ),
        httpx.Response(200, json=[]),
    ]

    guide = await hdhomerun_client.fetch_full_guide(TUNER_SETTINGS, "hdhomerun")
    assert guide is not None
    assert len(guide) == 1
    assert guide[0]["channel_number"] == "4.1"
    assert guide[0]["airings"][0]["series_id"] == "C101"


@respx.mock
def test_api_recording_rules_endpoints(client):
    from app.plugins.base import registry
    from app.plugins.hdhomerun.plugin import HDHomeRunPlugin

    plugin = HDHomeRunPlugin(
        {
            "id": "hdhomerun",
            "settings": {"tuner_host": "hdhr.local", "tuner_port": 80, "dvr_host": "", "dvr_port": 50000},
        }
    )
    registry.register(plugin)

    respx.get("http://hdhr.local:80/discover.json").mock(
        return_value=httpx.Response(200, json={"DeviceAuth": "test_auth_token"})
    )
    respx.post("https://api.hdhomerun.com/api/recording_rules").mock(
        return_value=httpx.Response(200, json=[{"RecordingRuleID": "999", "SeriesID": "S999"}])
    )

    res = client.post(
        "/api/hdhomerun/hdhomerun/recording-rules",
        json={"series_id": "S999", "date_time": 1700000000, "channel": "4.1"},
    )
    assert res.status_code == 200
    assert res.json()[0]["RecordingRuleID"] == "999"

    res = client.delete("/api/hdhomerun/hdhomerun/recording-rules/999")
    assert res.status_code == 200
    assert res.json() == [{"RecordingRuleID": "999", "SeriesID": "S999"}]
