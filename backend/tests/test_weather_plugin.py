from __future__ import annotations

import httpx
import respx

from app.plugins.weather.plugin import FORECAST_URL, WeatherPlugin, _condition_for

FAKE_RESPONSE = {
    "current": {"temperature_2m": 72.5, "weather_code": 1},
    "daily": {
        "time": ["2026-07-24", "2026-07-25"],
        "temperature_2m_max": [85.0, 88.0],
        "temperature_2m_min": [68.0, 70.0],
        "weather_code": [1, 61],
    },
}


def make_plugin() -> WeatherPlugin:
    return WeatherPlugin(
        {
            "id": "weather",
            "settings": {
                "latitude": 32.7555,
                "longitude": -97.3308,
                "location_name": "Fort Worth, TX",
                "units": "fahrenheit",
            },
        }
    )


def test_condition_for_known_code():
    assert _condition_for(1) == "Mainly clear"


def test_condition_for_unknown_code_falls_back():
    assert _condition_for(999) == "Unknown"


@respx.mock
async def test_get_summary_maps_current_conditions():
    respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary == {
        "location_name": "Fort Worth, TX",
        "temperature": 72.5,
        "condition": "Mainly clear",
    }


@respx.mock
async def test_get_detail_includes_daily_forecast():
    respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["temperature"] == 72.5
    assert detail["daily_forecast"] == [
        {"date": "2026-07-24", "high": 85.0, "low": 68.0, "condition": "Mainly clear"},
        {"date": "2026-07-25", "high": 88.0, "low": 70.0, "condition": "Slight rain"},
    ]


@respx.mock
async def test_get_ai_tools_exposes_weather_summary_tool():
    respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))
    plugin = make_plugin()

    tools = plugin.get_ai_tools()

    assert len(tools) == 1
    assert tools[0].name == "get_weather_summary"
    result = await tools[0].handler()
    assert result["condition"] == "Mainly clear"


@respx.mock
async def test_fetch_uses_celsius_when_configured():
    route = respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))
    plugin = WeatherPlugin({"id": "weather", "settings": {"latitude": 0, "longitude": 0, "units": "celsius"}})

    await plugin.get_summary()

    assert route.calls.last.request.url.params["temperature_unit"] == "celsius"
