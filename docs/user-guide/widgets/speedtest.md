# Speedtest Widget

The **Speedtest** widget (`type: speedtest`) measures your internet connection speed against Speedtest.net servers and records latency and throughput trends over time.

---

## Features

- **Key Metrics**: Measures download bandwidth (Mbps), upload bandwidth (Mbps), and ping latency (ms).
- **Scheduled Automated Testing**: Runs in the background on a configurable interval (e.g. every 60 minutes).
- **Manual "Run Now"**: Tap the tile and hit **Run now** to perform an instant test.
- **Historical Trends**: View a timestamped history log of recent speed measurements.

---

## Configuration (`dashboard.yaml`)

```yaml
- id: speedtest
  type: speedtest
  enabled: true
  layout: { col: 3, row: 14, colSpan: 2, rowSpan: 1 }
  settings:
    title: "Speedtest"
    interval_minutes: 60 # Run background test every N minutes
```
