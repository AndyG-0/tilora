from __future__ import annotations

import httpx
import respx

import app.scheduler as scheduler_module
from app.integrations import nws_client
from app.plugins.alert.plugin import AlertPlugin
from app.plugins.base import registry
from app.plugins.weather.plugin import (
    FORECAST_URL,
    WeatherPlugin,
    _forecast_severe_weather_signals,
    _map_nws_severity,
)
from app.storage import db

FAKE_NWS_RESPONSE = {
    "features": [
        {
            "properties": {
                "id": "urn:oid:nws-1",
                "event": "Tornado Warning",
                "headline": "Tornado Warning issued for the area",
                "severity": "Extreme",
            }
        }
    ]
}

FAKE_FORECAST_RESPONSE = {
    "current": {"temperature_2m": 72.5, "weather_code": 1},
    "daily": {
        "time": ["2026-07-24", "2026-07-25"],
        "temperature_2m_max": [85.0, 88.0],
        "temperature_2m_min": [68.0, 70.0],
        "weather_code": [95, 1],
        "wind_speed_10m_max": [20.0, 55.0],
    },
}


def make_plugin(**settings) -> WeatherPlugin:
    return WeatherPlugin(
        {
            "id": "weather",
            "settings": {
                "latitude": 32.7555,
                "longitude": -97.3308,
                "location_name": "Fort Worth, TX",
                "units": "fahrenheit",
                **settings,
            },
        }
    )


def make_alert_plugin() -> AlertPlugin:
    return AlertPlugin({"id": "alert", "settings": {}})


# --- nws_client -------------------------------------------------------------


@respx.mock
async def test_get_active_alerts_parses_features():
    respx.get(nws_client.ALERTS_URL).mock(return_value=httpx.Response(200, json=FAKE_NWS_RESPONSE))

    alerts = await nws_client.get_active_alerts(32.7555, -97.3308)

    assert alerts == [
        {
            "id": "urn:oid:nws-1",
            "event": "Tornado Warning",
            "headline": "Tornado Warning issued for the area",
            "severity": "Extreme",
        }
    ]


@respx.mock
async def test_get_active_alerts_returns_empty_outside_coverage():
    respx.get(nws_client.ALERTS_URL).mock(return_value=httpx.Response(200, json={"features": []}))

    alerts = await nws_client.get_active_alerts(48.8566, 2.3522)

    assert alerts == []


@respx.mock
async def test_get_active_alerts_raises_nws_error_on_http_failure():
    respx.get(nws_client.ALERTS_URL).mock(return_value=httpx.Response(500))

    try:
        await nws_client.get_active_alerts(32.7555, -97.3308)
        raise AssertionError("expected NWSError")
    except nws_client.NWSError:
        pass


# --- _forecast_severe_weather_signals / _map_nws_severity -------------------


def test_forecast_severe_weather_signals_flags_severe_weather_code():
    daily = {"time": ["2026-07-24"], "weather_code": [95], "wind_speed_10m_max": [10.0]}

    signals = _forecast_severe_weather_signals(daily, "Fort Worth, TX")

    assert signals == [
        {
            "key": "forecast:2026-07-24:code:95",
            "severity": "warning",
            "message": "Thunderstorm expected 2026-07-24 for Fort Worth, TX.",
        }
    ]


def test_forecast_severe_weather_signals_flags_high_wind():
    daily = {"time": ["2026-07-24"], "weather_code": [1], "wind_speed_10m_max": [55.0]}

    signals = _forecast_severe_weather_signals(daily, "Fort Worth, TX")

    assert signals == [
        {
            "key": "forecast:2026-07-24:wind",
            "severity": "warning",
            "message": "High winds expected 2026-07-24 for Fort Worth, TX (up to 55 mph).",
        }
    ]


def test_forecast_severe_weather_signals_empty_for_calm_clear_day():
    daily = {"time": ["2026-07-24"], "weather_code": [1], "wind_speed_10m_max": [10.0]}

    assert _forecast_severe_weather_signals(daily, "Fort Worth, TX") == []


def test_map_nws_severity():
    assert _map_nws_severity("Extreme") == "critical"
    assert _map_nws_severity("Severe") == "critical"
    assert _map_nws_severity("Moderate") == "warning"
    assert _map_nws_severity("Minor") == "info"
    assert _map_nws_severity("Unknown") == "info"
    assert _map_nws_severity(None) == "info"


# --- WeatherPlugin.get_severe_weather_signals --------------------------------


@respx.mock
async def test_get_severe_weather_signals_combines_nws_and_forecast():
    respx.get(nws_client.ALERTS_URL).mock(return_value=httpx.Response(200, json=FAKE_NWS_RESPONSE))
    respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=FAKE_FORECAST_RESPONSE))
    plugin = make_plugin()

    signals = await plugin.get_severe_weather_signals()

    keys = {signal["key"] for signal in signals}
    assert "nws:urn:oid:nws-1" in keys
    assert "forecast:2026-07-24:code:95" in keys
    assert "forecast:2026-07-25:wind" in keys


@respx.mock
async def test_get_severe_weather_signals_swallows_nws_errors():
    respx.get(nws_client.ALERTS_URL).mock(return_value=httpx.Response(500))
    respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=FAKE_FORECAST_RESPONSE))
    plugin = make_plugin()

    signals = await plugin.get_severe_weather_signals()

    assert all(not signal["key"].startswith("nws:") for signal in signals)
    assert any(signal["key"].startswith("forecast:") for signal in signals)


# --- scheduler.run_severe_weather_check --------------------------------------


async def test_run_severe_weather_check_creates_alert_for_new_signal(tmp_db, monkeypatch):
    weather_plugin = make_plugin()
    registry.register(weather_plugin)
    registry.register(make_alert_plugin())

    async def fake_signals(self):
        return [{"key": "nws:abc", "severity": "critical", "message": "Tornado Warning"}]

    monkeypatch.setattr(WeatherPlugin, "get_severe_weather_signals", fake_signals)

    await scheduler_module.run_severe_weather_check(weather_plugin)

    alerts = db.list_active_alerts(scheduler_module.ALERT_WIDGET_ID)
    assert len(alerts) == 1
    assert alerts[0]["message"] == "Tornado Warning"
    assert alerts[0]["severity"] == "critical"
    assert db.has_seen_severe_weather_alert(weather_plugin.id, "nws:abc")


async def test_run_severe_weather_check_dedups_on_second_poll(tmp_db, monkeypatch):
    weather_plugin = make_plugin()
    registry.register(weather_plugin)
    registry.register(make_alert_plugin())

    async def fake_signals(self):
        return [{"key": "nws:abc", "severity": "critical", "message": "Tornado Warning"}]

    monkeypatch.setattr(WeatherPlugin, "get_severe_weather_signals", fake_signals)

    await scheduler_module.run_severe_weather_check(weather_plugin)
    await scheduler_module.run_severe_weather_check(weather_plugin)

    alerts = db.list_active_alerts(scheduler_module.ALERT_WIDGET_ID)
    assert len(alerts) == 1


async def test_run_severe_weather_check_noop_when_disabled(tmp_db, monkeypatch):
    weather_plugin = make_plugin(severe_weather_alerts=False)
    registry.register(weather_plugin)
    registry.register(make_alert_plugin())
    called = False

    async def fake_signals(self):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(WeatherPlugin, "get_severe_weather_signals", fake_signals)

    await scheduler_module.run_severe_weather_check(weather_plugin)

    assert called is False
    assert db.list_active_alerts(scheduler_module.ALERT_WIDGET_ID) == []


async def test_run_severe_weather_check_noop_when_no_alert_widget(tmp_db, monkeypatch):
    weather_plugin = make_plugin()
    registry.register(weather_plugin)
    called = False

    async def fake_signals(self):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(WeatherPlugin, "get_severe_weather_signals", fake_signals)

    await scheduler_module.run_severe_weather_check(weather_plugin)  # must not raise

    assert called is False


async def test_run_severe_weather_check_swallows_exceptions(tmp_db, monkeypatch):
    weather_plugin = make_plugin()
    registry.register(weather_plugin)
    registry.register(make_alert_plugin())

    async def failing_signals(self):
        raise RuntimeError("network unreachable")

    monkeypatch.setattr(WeatherPlugin, "get_severe_weather_signals", failing_signals)

    await scheduler_module.run_severe_weather_check(weather_plugin)  # must not raise

    assert db.list_active_alerts(scheduler_module.ALERT_WIDGET_ID) == []


# --- scheduler job registration ----------------------------------------------


def test_schedule_severe_weather_widgets_only_schedules_weather_plugins():
    from app.plugins.speedtest.plugin import SpeedtestPlugin

    registry.register(make_plugin())
    registry.register(SpeedtestPlugin({"id": "speedtest", "settings": {"title": "Speedtest", "interval_minutes": 60}}))

    scheduler_module.schedule_severe_weather_widgets()
    try:
        job_ids = {job.id for job in scheduler_module.scheduler.get_jobs()}
        assert job_ids == {"severe-weather:weather"}
    finally:
        scheduler_module.scheduler.remove_all_jobs()


def test_schedule_severe_weather_widget_uses_15_minute_interval():
    plugin = make_plugin()

    scheduler_module.schedule_severe_weather_widget(plugin)
    try:
        job = scheduler_module.scheduler.get_job("severe-weather:weather")
        assert job.trigger.interval.total_seconds() == 15 * 60
    finally:
        scheduler_module.scheduler.remove_all_jobs()


def test_unschedule_widget_removes_severe_weather_job():
    plugin = make_plugin()
    scheduler_module.schedule_severe_weather_widget(plugin)
    try:
        scheduler_module.unschedule_widget("weather")

        assert scheduler_module.scheduler.get_job("severe-weather:weather") is None
    finally:
        scheduler_module.scheduler.remove_all_jobs()
