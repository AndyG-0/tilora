# Synology NAS Widget

The **Synology** widget (`type: synology`) connects to Synology DiskStation Manager (DSM) to monitor storage volume capacity, storage pool health, CPU temperature, and system uptime.

---

## Features

- **Storage Pool & Volume Metrics**: Real-time display of total capacity, used storage, free space, and percentage utilization.
- **Drive & Volume Health**: Healthy / Degraded / Warning status badges.
- **System Health**: Reports hardware model, DSM version, CPU temperature, and uptime in days.

---

## Configuration

Configure host and credentials under **Settings → Admin settings → Synology** (or in `dashboard.yaml`):

```yaml
- id: synology
  type: synology
  enabled: true
  layout: { col: 1, row: 13, colSpan: 2, rowSpan: 1 }
  settings:
    host: "synology.local"
    port: 5000
    use_https: false
    username: "admin"
```
