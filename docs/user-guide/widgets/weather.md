# Weather Widget

The **Weather** widget (`type: weather`) delivers real-time weather observations, hourly and 7-day forecasts, air quality index, pollen counts, and severe weather alert banners powered by Open-Meteo.

---

## Features

- **Current Conditions**: Temperature, "feels like" apparent temperature, condition icon, humidity, wind speed, UV index, and precipitation probability.
- **Hourly & Daily Forecasts**: Interactive temperature charts and 7-day outlook.
- **Air Quality (AQI)**: PM2.5, PM10, ozone, and European AQI metrics.
- **Pollen Counts**: Tracks grass, birch, alder, mugwort, olive, and ragweed pollen levels.
- **Severe Weather Alerts**: Displays urgent storm and flood warnings issued by national meteorological agencies.
- **AI Tool Integration**: Exposes `get_weather_summary` and `get_weather_forecast` to the AI assistant.
- **Zero API Key**: Open-Meteo provides free, open weather data without requiring an API key.

---

## Configuration (`dashboard.yaml`)

```yaml
- id: weather
  type: weather
  enabled: true
  layout: { col: 1, row: 1, colSpan: 1, rowSpan: 1 }
  settings:
    latitude: 32.7555
    longitude: -97.3308
    location_name: "Fort Worth, TX"
    units: fahrenheit # "fahrenheit" or "celsius"
```
