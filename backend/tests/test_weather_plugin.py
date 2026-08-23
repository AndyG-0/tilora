from __future__ import annotations

import httpx
import respx

from app.plugins.weather.plugin import (
    AIR_QUALITY_URL,
    FORECAST_URL,
    WeatherPlugin,
    _aqi_category_for,
    _condition_for,
    _primary_pollutant,
)

FAKE_RESPONSE = {
    "current": {"temperature_2m": 72.5, "weather_code": 1, "is_day": 1},
    "daily": {
        "time": ["2026-07-24", "2026-07-25"],
        "temperature_2m_max": [85.0, 88.0],
        "temperature_2m_min": [68.0, 70.0],
        "weather_code": [1, 61],
    },
}

FAKE_AIR_QUALITY_RESPONSE = {
    "current": {
        "us_aqi": 42,
        "pm2_5": 8.1,
        "pm10": 15.0,
        "ozone": 30.0,
        "alder_pollen": None,
        "birch_pollen": None,
        "grass_pollen": None,
        "mugwort_pollen": None,
        "olive_pollen": None,
        "ragweed_pollen": None,
    }
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


def test_settings_scope_is_personal():
    # Each household member's location is their own, not shared — see
    # Plugin.settings_scope.
    assert WeatherPlugin.settings_scope == "personal"


def test_condition_for_known_code():
    assert _condition_for(1, "en") == "Mainly clear"


def test_condition_for_unknown_code_falls_back():
    assert _condition_for(999, "en") == "Unknown"


def test_condition_for_known_code_translates_by_locale():
    assert _condition_for(1, "es") == "Mayormente despejado"
    assert _condition_for(1, "fr") == "Généralement dégagé"
    assert _condition_for(1, "de") == "Überwiegend klar"


def test_condition_for_missing_locale_falls_back_to_english():
    assert _condition_for(1, "xx") == "Mainly clear"


@respx.mock
async def test_get_summary_maps_current_conditions():
    respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary == {
        "location_name": "Fort Worth, TX",
        "temperature": 72.5,
        "condition": "Mainly clear",
        "weather_code": 1,
        "is_day": True,
    }


@respx.mock
async def test_get_detail_includes_daily_forecast():
    forecast_route = respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))
    respx.get(AIR_QUALITY_URL).mock(return_value=httpx.Response(200, json=FAKE_AIR_QUALITY_RESPONSE))
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["temperature"] == 72.5
    assert detail["daily_forecast"] == [
        {"date": "2026-07-24", "high": 85.0, "low": 68.0, "condition": "Mainly clear", "weather_code": 1},
        {"date": "2026-07-25", "high": 88.0, "low": 70.0, "condition": "Slight rain", "weather_code": 61},
    ]
    # Regression: get_detail() must share the one forecast fetch with
    # get_summary() rather than redundantly re-fetching it.
    assert forecast_route.call_count == 1


@respx.mock
async def test_get_detail_includes_latitude_and_longitude():
    respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))
    respx.get(AIR_QUALITY_URL).mock(return_value=httpx.Response(200, json=FAKE_AIR_QUALITY_RESPONSE))
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["latitude"] == 32.7555
    assert detail["longitude"] == -97.3308


@respx.mock
async def test_get_detail_includes_severe_weather_alerts_setting():
    respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))
    respx.get(AIR_QUALITY_URL).mock(return_value=httpx.Response(200, json=FAKE_AIR_QUALITY_RESPONSE))
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["severe_weather_alerts"] is True


@respx.mock
async def test_get_detail_reflects_severe_weather_alerts_disabled():
    respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))
    respx.get(AIR_QUALITY_URL).mock(return_value=httpx.Response(200, json=FAKE_AIR_QUALITY_RESPONSE))
    plugin = WeatherPlugin(
        {
            "id": "weather",
            "settings": {
                "latitude": 32.7555,
                "longitude": -97.3308,
                "location_name": "Fort Worth, TX",
                "units": "fahrenheit",
                "severe_weather_alerts": False,
            },
        }
    )

    detail = await plugin.get_detail()

    assert detail["severe_weather_alerts"] is False


@respx.mock
async def test_get_ai_tools_exposes_weather_summary_tool():
    respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))
    plugin = make_plugin()

    tools = plugin.get_ai_tools()

    assert len(tools) == 2
    assert tools[0].name == "get_weather_summary"
    result = await tools[0].handler()
    assert result["condition"] == "Mainly clear"
    assert tools[1].name == "show_weather_detail"
    assert tools[1].is_navigation is True
    nav_result = await tools[1].handler()
    assert nav_result == {"widget_id": plugin.id, "panel": None}


@respx.mock
async def test_fetch_uses_celsius_when_configured():
    route = respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))
    plugin = WeatherPlugin({"id": "weather", "settings": {"latitude": 0, "longitude": 0, "units": "celsius"}})

    await plugin.get_summary()

    assert route.calls.last.request.url.params["temperature_unit"] == "celsius"


def test_aqi_category_for_breakpoints():
    assert _aqi_category_for(0, "en") == "Good"
    assert _aqi_category_for(50, "en") == "Good"
    assert _aqi_category_for(51, "en") == "Moderate"
    assert _aqi_category_for(100, "en") == "Moderate"
    assert _aqi_category_for(101, "en") == "Unhealthy for sensitive groups"
    assert _aqi_category_for(151, "en") == "Unhealthy"
    assert _aqi_category_for(201, "en") == "Very unhealthy"
    assert _aqi_category_for(301, "en") == "Hazardous"


def test_aqi_category_for_translates_by_locale():
    assert _aqi_category_for(0, "es") == "Buena"
    assert _aqi_category_for(0, "fr") == "Bonne"
    assert _aqi_category_for(0, "de") == "Gut"


def test_primary_pollutant_picks_highest_ratio_to_its_ceiling():
    # pm2_5 ceiling 12.0 -> ratio 2.0; pm10 ceiling 54.0 -> ratio ~0.5; ozone ceiling 100.0 -> ratio 0.3
    current = {"pm2_5": 24.0, "pm10": 27.0, "ozone": 30.0}
    assert _primary_pollutant(current) == "pm2_5"


def test_primary_pollutant_returns_none_when_no_pollutants_present():
    assert _primary_pollutant({}) is None


@respx.mock
async def test_get_detail_includes_air_quality():
    respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))
    respx.get(AIR_QUALITY_URL).mock(return_value=httpx.Response(200, json=FAKE_AIR_QUALITY_RESPONSE))
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["air_quality"] == {
        "us_aqi": 42,
        "us_aqi_category": "Good",
        "pm2_5": 8.1,
        "pm10": 15.0,
        "ozone": 30.0,
        "primary_pollutant": "pm2_5",
    }
    assert "pollen" not in detail["air_quality"]


@respx.mock
async def test_get_detail_includes_pollen_when_present():
    respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))
    response = {**FAKE_AIR_QUALITY_RESPONSE, "current": {**FAKE_AIR_QUALITY_RESPONSE["current"], "birch_pollen": 12.5}}
    respx.get(AIR_QUALITY_URL).mock(return_value=httpx.Response(200, json=response))
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["air_quality"]["pollen"] == {"birch_pollen": 12.5}


@respx.mock
async def test_get_detail_omits_air_quality_when_us_aqi_missing():
    respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))
    response = {"current": {"us_aqi": None}}
    respx.get(AIR_QUALITY_URL).mock(return_value=httpx.Response(200, json=response))
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert "air_quality" not in detail


@respx.mock
async def test_get_detail_omits_air_quality_on_fetch_error():
    respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))
    respx.get(AIR_QUALITY_URL).mock(return_value=httpx.Response(500))
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert "air_quality" not in detail


def test_get_ai_tools_default_and_custom_instances():
    default_plugin = WeatherPlugin({"id": "weather", "settings": {"location_name": "Austin, TX"}})
    default_tools = default_plugin.get_ai_tools()
    assert len(default_tools) == 2
    assert default_tools[0].name == "get_weather_summary"
    assert "Austin, TX" in default_tools[0].description
    assert default_tools[1].name == "show_weather_detail"
    assert "Austin, TX" in default_tools[1].description

    custom_plugin = WeatherPlugin({"id": "weather-custom-123", "settings": {"location_name": "London, UK"}})
    custom_tools = custom_plugin.get_ai_tools()
    assert len(custom_tools) == 2
    assert custom_tools[0].name == "get_weather_summary_weather_custom_123"
    assert "London, UK" in custom_tools[0].description
    assert custom_tools[1].name == "show_weather_detail_weather_custom_123"
    assert "London, UK" in custom_tools[1].description
