# Mapping & Directions Widget

The **Mapping** widget (`type: mapping`) provides interactive Leaflet maps, point-to-point route directions (driving, walking, cycling), and nearby Point of Interest (POI) discovery via OpenStreetMap and Overpass.

---

## Features

- **Interactive Leaflet Map**: Smooth panning, zooming, and location pinning.
- **Directions & Navigation**: Calculate driving, walking, or cycling directions with turn-by-turn routes and distance estimates.
- **Nearby Places (POI)**: Find nearby restaurants, cafes, grocery stores, gas stations, pharmacies, hospitals, banks, and parks around your home or current location.
- **Privacy First**: Uses open-source OpenStreetMap and Overpass API data without third-party tracking.

---

## Configuration (`dashboard.yaml`)

```yaml
- id: mapping
  type: mapping
  enabled: true
  layout: { col: 1, row: 7, colSpan: 2, rowSpan: 1 }
  settings:
    latitude: 32.7555
    longitude: -97.3308
    location_name: "Fort Worth, TX"
```
