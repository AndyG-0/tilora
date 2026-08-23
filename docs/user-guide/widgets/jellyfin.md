# Jellyfin Media Server Widget

The **Jellyfin** widget (`type: jellyfin`) integrates with self-hosted Jellyfin media servers to showcase recently added media, in-progress viewing sessions, and control playback.

---

## Features

- **Recently Added Media**: Displays posters, episode titles, and metadata for new movies, shows, and music.
- **Active Playback Sessions**: Shows live playback progress, client names, and transcoding status across your home network.
- **In-App Streaming**: Play audio and video directly inside the dashboard using Direct Play or HLS transcoding.
- **Authentication**: Supports server-wide admin API keys or user account login with permission awareness.

---

## Configuration

Configure host and credentials under **Settings → Admin settings → Jellyfin** or in `dashboard.yaml`:

```yaml
- id: jellyfin
  type: jellyfin
  enabled: true
  layout: { col: 3, row: 9, colSpan: 2, rowSpan: 1 }
  settings:
    host: "jellyfin.local"
    port: 8096
    use_https: false
    auth_mode: api_key # "api_key" or "password"
    library_ids: [] # Optional: limit to specific library folders
```
