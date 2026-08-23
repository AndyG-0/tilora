# Flights (ADS-B / Radar) Widget

The **Flights** widget (`type: flights`) tracks aircraft flying overhead in real time using public OpenSky Network ADS-B telemetry data.

---

## Features

- **Live Overhead Radar**: Displays aircraft within a configurable radius of your coordinates.
- **Aircraft Telemetry**: Shows callsign, flight route (origin/destination), altitude, ground speed, and heading.
- **Visual Aircraft Icons & Photos**: Automatically determines aircraft category (Jet, Propeller, Helicopter) and renders high-quality aircraft photos and commercial airline logos.
- **Interactive Map View**: Tap the tile to view an interactive Leaflet radar map tracking live flight paths.

---

## Configuration (`dashboard.yaml`)

```yaml
- id: flights
  type: flights
  enabled: true
  layout: { col: 2, row: 1, colSpan: 2, rowSpan: 1 }
  settings:
    latitude: 32.7555
    longitude: -97.3308
    location_name: "Fort Worth, TX"
    radius_nm: 15 # Search radius in nautical miles
```
