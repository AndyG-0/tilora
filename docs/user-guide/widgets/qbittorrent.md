# qBittorrent Widget

The **qBittorrent** widget (`type: qbittorrent`) connects to the qBittorrent WebUI to monitor active torrent downloads, upload/download bandwidth, and torrent states.

---

## Features

- **Live Speeds**: Displays combined real-time download and upload speeds.
- **Status Counts**: View counts of active, downloading, seeding, paused, and completed torrents.
- **Torrent Details**: Tap the tile to view individual torrent names, progress bars, ETA, seeders, and file sizes.

---

## Configuration

Configure host and credentials under **Settings → Admin settings → qBittorrent** (or in `dashboard.yaml`):

```yaml
- id: qbittorrent
  type: qbittorrent
  enabled: true
  layout: { col: 1, row: 14, colSpan: 2, rowSpan: 1 }
  settings:
    host: "qbittorrent.local"
    port: 8080
    use_https: false
    username: "admin"
```
