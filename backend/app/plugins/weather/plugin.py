"""Weather plugin, backed by Open-Meteo (no API key required)."""

from __future__ import annotations

from typing import Any

import httpx

from app.plugins.base import Plugin, ToolDef

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# https://open-meteo.com/en/docs#weathervariables (WMO weather codes)
_CONDITION_BY_CODE = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
}


def _condition_for(code: int) -> str:
    return _CONDITION_BY_CODE.get(code, "Unknown")


class WeatherPlugin(Plugin):
    id = "weather"
    name = "Weather"
    refresh_interval_seconds = 600

    async def _fetch(self) -> dict[str, Any]:
        settings = self.config["settings"]
        temp_unit = "fahrenheit" if settings.get("units", "fahrenheit") == "fahrenheit" else "celsius"
        params = {
            "latitude": settings["latitude"],
            "longitude": settings["longitude"],
            "current": "temperature_2m,weather_code",
            "hourly": "temperature_2m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,weather_code",
            "temperature_unit": temp_unit,
            "timezone": "auto",
            "forecast_days": 5,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(FORECAST_URL, params=params)
            response.raise_for_status()
            return response.json()

    async def get_summary(self) -> dict[str, Any]:
        data = await self._fetch()
        current = data["current"]
        return {
            "location_name": self.config["settings"].get("location_name", "Your location"),
            "temperature": current["temperature_2m"],
            "condition": _condition_for(current["weather_code"]),
        }

    async def get_detail(self) -> dict[str, Any]:
        data = await self._fetch()
        daily = data["daily"]
        forecast = [
            {
                "date": daily["time"][i],
                "high": daily["temperature_2m_max"][i],
                "low": daily["temperature_2m_min"][i],
                "condition": _condition_for(daily["weather_code"][i]),
            }
            for i in range(len(daily["time"]))
        ]
        summary = await self.get_summary()
        return {**summary, "daily_forecast": forecast}

    def get_ai_tools(self) -> list[ToolDef]:
        async def get_weather_summary() -> dict[str, Any]:
            return await self.get_summary()

        return [
            ToolDef(
                name="get_weather_summary",
                description=(
                    "Get the current temperature and weather condition for the dashboard's configured location."
                ),
                parameters={"type": "object", "properties": {}},
                handler=get_weather_summary,
            )
        ]
