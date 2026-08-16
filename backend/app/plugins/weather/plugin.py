"""Weather plugin, backed by Open-Meteo (no API key required)."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

import httpx

from app.i18n import t
from app.integrations import nws_client
from app.plugins.base import Plugin, ToolDef

logger = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# Open-Meteo's pollen fields only cover Europe — requested anyway since the
# API just omits/nulls them elsewhere, which _fetch_air_quality() filters out.
_POLLEN_FIELDS = ("alder_pollen", "birch_pollen", "grass_pollen", "mugwort_pollen", "olive_pollen", "ragweed_pollen")

# US AQI breakpoints (airnow.gov), used both for the category label and to
# pick which pollutant is driving the reading.
_AQI_CATEGORY_BREAKPOINTS = (
    (50, "weather.air_quality.good"),
    (100, "weather.air_quality.moderate"),
    (150, "weather.air_quality.unhealthy_sensitive"),
    (200, "weather.air_quality.unhealthy"),
    (300, "weather.air_quality.very_unhealthy"),
)
_AQI_CATEGORY_HAZARDOUS = "weather.air_quality.hazardous"

# Rough "good" ceilings (µg/m³) for each pollutant, used only to pick which
# one is most elevated relative to its own healthy range — not a real EPA
# sub-index calculation.
_POLLUTANT_GOOD_CEILING = {"pm2_5": 12.0, "pm10": 54.0, "ozone": 100.0}


def _aqi_category_for(us_aqi: float, locale: str) -> str:
    for ceiling, key in _AQI_CATEGORY_BREAKPOINTS:
        if us_aqi <= ceiling:
            return t(key, locale)
    return t(_AQI_CATEGORY_HAZARDOUS, locale)


def _primary_pollutant(current: dict[str, Any]) -> str | None:
    ratios = {
        name: current[name] / ceiling
        for name, ceiling in _POLLUTANT_GOOD_CEILING.items()
        if current.get(name) is not None
    }
    return max(ratios, key=ratios.get) if ratios else None


# https://open-meteo.com/en/docs#weathervariables (WMO weather codes)
_CONDITION_KEY_BY_CODE = {
    0: "weather.condition.clear_sky",
    1: "weather.condition.mainly_clear",
    2: "weather.condition.partly_cloudy",
    3: "weather.condition.overcast",
    45: "weather.condition.fog",
    48: "weather.condition.depositing_rime_fog",
    51: "weather.condition.light_drizzle",
    53: "weather.condition.moderate_drizzle",
    55: "weather.condition.dense_drizzle",
    61: "weather.condition.slight_rain",
    63: "weather.condition.moderate_rain",
    65: "weather.condition.heavy_rain",
    71: "weather.condition.slight_snow",
    73: "weather.condition.moderate_snow",
    75: "weather.condition.heavy_snow",
    80: "weather.condition.slight_rain_showers",
    81: "weather.condition.moderate_rain_showers",
    82: "weather.condition.violent_rain_showers",
    95: "weather.condition.thunderstorm",
}


def _condition_for(code: int, locale: str) -> str:
    key = _CONDITION_KEY_BY_CODE.get(code, "weather.condition.unknown")
    return t(key, locale)


# WMO codes worth flagging as severe, used as a forecast-based fallback for
# non-US locations (NWS only covers the US, so nws_client returns nothing
# there) — see _forecast_severe_weather_signals.
_SEVERE_WEATHER_EVENT_BY_CODE = {
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Severe thunderstorm with hail",
    75: "Heavy snow",
}
_HIGH_WIND_THRESHOLD_MPH = 50.0


def _forecast_severe_weather_signals(daily: dict[str, Any], location_name: str) -> list[dict[str, str]]:
    dates = daily["time"]
    codes = daily["weather_code"]
    winds = daily.get("wind_speed_10m_max") or [None] * len(dates)
    signals: list[dict[str, str]] = []
    for i, date in enumerate(dates):
        event = _SEVERE_WEATHER_EVENT_BY_CODE.get(codes[i])
        if event is not None:
            signals.append(
                {
                    "key": f"forecast:{date}:code:{codes[i]}",
                    "severity": "warning",
                    "message": f"{event} expected {date} for {location_name}.",
                }
            )
        wind = winds[i] if i < len(winds) else None
        if wind is not None and wind >= _HIGH_WIND_THRESHOLD_MPH:
            signals.append(
                {
                    "key": f"forecast:{date}:wind",
                    "severity": "warning",
                    "message": f"High winds expected {date} for {location_name} (up to {round(wind)} mph).",
                }
            )
    return signals


def _map_nws_severity(nws_severity: str | None) -> str:
    if nws_severity in ("Extreme", "Severe"):
        return "critical"
    if nws_severity == "Moderate":
        return "warning"
    return "info"


class WeatherPlugin(Plugin):
    id = "weather"
    name = "Weather"
    refresh_interval_seconds = 600
    # Each household member cares about their own location, not a shared
    # one — see Plugin.settings_scope.
    settings_scope = "personal"
    # A widget added via the UI has no dashboard.yaml entry to source
    # settings from, so it starts here — same Fort Worth, TX default as
    # dashboard.example.yaml — and the user swaps in their own city via the
    # detail view's "Change city" search. Without this, a freshly-added
    # widget has no latitude/longitude and 500s before that UI can load.
    default_settings: ClassVar[dict[str, Any]] = {
        "latitude": 32.7555,
        "longitude": -97.3308,
        "location_name": "Fort Worth, TX",
        "units": "fahrenheit",
        "severe_weather_alerts": True,
    }

    async def _fetch(self) -> dict[str, Any]:
        settings = self.config["settings"]
        temp_unit = "fahrenheit" if settings.get("units", "fahrenheit") == "fahrenheit" else "celsius"
        params = {
            "latitude": settings["latitude"],
            "longitude": settings["longitude"],
            "current": "temperature_2m,weather_code,is_day",
            "hourly": "temperature_2m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,weather_code,wind_speed_10m_max",
            "temperature_unit": temp_unit,
            "wind_speed_unit": "mph",
            "timezone": "auto",
            "forecast_days": 5,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(FORECAST_URL, params=params)
            response.raise_for_status()
            return response.json()

    def _build_summary(self, current: dict[str, Any]) -> dict[str, Any]:
        return {
            "location_name": self.config["settings"].get("location_name", "Your location"),
            "temperature": current["temperature_2m"],
            "condition": _condition_for(current["weather_code"], self.locale),
            "weather_code": current["weather_code"],
            "is_day": bool(current["is_day"]),
        }

    async def get_summary(self) -> dict[str, Any]:
        data = await self._fetch()
        return self._build_summary(data["current"])

    async def _fetch_air_quality(self) -> dict[str, Any] | None:
        settings = self.config["settings"]
        params = {
            "latitude": settings["latitude"],
            "longitude": settings["longitude"],
            "current": "us_aqi,pm2_5,pm10,ozone," + ",".join(_POLLEN_FIELDS),
            "timezone": "auto",
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(AIR_QUALITY_URL, params=params)
                response.raise_for_status()
                current = response.json()["current"]
        except httpx.HTTPError as exc:
            logger.warning("Could not fetch air quality for widget '%s': %s", self.id, exc)
            return None

        if current.get("us_aqi") is None:
            return None

        result = {
            "us_aqi": current["us_aqi"],
            "us_aqi_category": _aqi_category_for(current["us_aqi"], self.locale),
            "pm2_5": current.get("pm2_5"),
            "pm10": current.get("pm10"),
            "ozone": current.get("ozone"),
            "primary_pollutant": _primary_pollutant(current),
        }
        pollen = {field: current[field] for field in _POLLEN_FIELDS if current.get(field) is not None}
        if pollen:
            result["pollen"] = pollen
        return result

    async def get_detail(self) -> dict[str, Any]:
        data = await self._fetch()
        daily = data["daily"]
        forecast = [
            {
                "date": daily["time"][i],
                "high": daily["temperature_2m_max"][i],
                "low": daily["temperature_2m_min"][i],
                "condition": _condition_for(daily["weather_code"][i], self.locale),
                "weather_code": daily["weather_code"][i],
            }
            for i in range(len(daily["time"]))
        ]
        summary = self._build_summary(data["current"])
        detail = {
            **summary,
            "daily_forecast": forecast,
            "severe_weather_alerts": self.config["settings"].get("severe_weather_alerts", True),
        }
        air_quality = await self._fetch_air_quality()
        if air_quality is not None:
            detail["air_quality"] = air_quality
        return detail

    async def get_severe_weather_signals(self) -> list[dict[str, str]]:
        """Combined severe-weather signals for the scheduler's severe-weather job.

        Live NWS alerts (US only) plus a WMO-weather-code/wind-speed
        heuristic derived from the forecast (works everywhere, since NWS
        doesn't cover locations outside the US) — see nws_client and
        _forecast_severe_weather_signals. Each signal has a stable `key` the
        caller uses to dedup against `db.severe_weather_seen`. Best-effort:
        a failure fetching either source is logged and simply yields fewer
        signals rather than raising, since this backs a background poll.
        """
        settings = self.config["settings"]
        location_name = settings.get("location_name", "your location")
        signals: list[dict[str, str]] = []

        try:
            alerts = await nws_client.get_active_alerts(settings["latitude"], settings["longitude"])
        except nws_client.NWSError as exc:
            logger.warning("Could not fetch NWS alerts for widget '%s': %s", self.id, exc)
            alerts = []
        signals.extend(
            {
                "key": f"nws:{alert['id']}",
                "severity": _map_nws_severity(alert.get("severity")),
                "message": alert.get("headline") or alert.get("event") or "Severe weather alert",
            }
            for alert in alerts
        )

        try:
            data = await self._fetch()
        except httpx.HTTPError as exc:
            logger.warning("Could not fetch forecast for severe-weather check on widget '%s': %s", self.id, exc)
            return signals
        signals.extend(_forecast_severe_weather_signals(data["daily"], location_name))
        return signals

    def get_ai_tools(self) -> list[ToolDef]:
        async def get_weather_summary() -> dict[str, Any]:
            return await self.get_summary()

        tool_name = (
            "get_weather_summary" if self.id == "weather" else f"get_weather_summary_{self.id.replace('-', '_')}"
        )
        location_name = self.config["settings"].get("location_name")
        desc = (
            f"Get the current temperature and weather condition for {location_name}."
            if location_name
            else "Get the current temperature and weather condition for the dashboard's configured location."
        )
        return [
            ToolDef(
                name=tool_name,
                description=desc,
                parameters={"type": "object", "properties": {}},
                handler=get_weather_summary,
            )
        ]
