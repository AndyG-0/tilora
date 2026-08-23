# Pi-hole Widget

The **Pi-hole** widget (`type: pihole`) connects to your network's Pi-hole DNS sinkhole (Pi-hole v6+ FTL REST API) to monitor domain blocking performance, query volume, and ad-blocking statistics.

---

## Features

- **DNS Ad-Blocking Metrics**: Displays total queries processed today, blocked queries count, and percentage blocked.
- **Top Blocked & Permitted Domains**: View the most frequent domain lookups and ad network blocks across your LAN.
- **Top Client Devices**: Identify which devices generate the most network DNS requests.
- **Gravity Status**: Real-time status indicator showing blocklist freshness.

---

## Configuration

Configure host and password under **Settings → Admin settings → Pi-hole** or in `dashboard.yaml`:

```yaml
- id: pihole
  type: pihole
  enabled: true
  layout: { col: 1, row: 10, colSpan: 1, rowSpan: 1 }
  settings:
    host: "pi.hole"
    port: 80
    use_https: false
```
