# Photos Slideshow Widget

The **Photos** widget (`type: photos`) turns your smart display into a digital photo frame, rotating family pictures, vacation albums, and wallpapers from multiple sources.

---

## Supported Photo Providers

1. **Local Filesystem (`local`)**:
    - Scans any folder of photos on the machine running the backend (supports JPG, PNG, WEBP, HEIC, TIFF).
    - Can scan subdirectories recursively.
2. **iCloud Shared Album (`icloud_shared`)**:
    - Uses a public iCloud Shared Album link (Photos app → Share Album → "Public Website").
    - Requires no Apple ID login on the server.
3. **iCloud Private Library (`icloud_private`)**:
    - Connects directly to your private Apple Photos library via your Apple ID and 2FA authentication.
    - Synchronizes any named album (e.g. *"Favorites"* or *"All Photos"*).
4. **Immich Self-Hosted Server (`immich`)**:
    - Connects to your self-hosted Immich photo server via API key.

---

## Configuration (`dashboard.yaml`)

```yaml
- id: photos
  type: photos
  enabled: true
  layout: { col: 3, row: 4, colSpan: 2, rowSpan: 1 }
  settings:
    provider: local # "local", "icloud_shared", "icloud_private", or "immich"
    directory: "/Volumes/Pictures/"
    recursive: true
    interval_seconds: 10 # Slideshow rotation interval
    index_refresh_seconds: 3600 # Background catalog rescan interval
```

---

## High-Performance Background Indexing

Tilora builds a local SQLite photo cache index in the background rather than scanning network shares on every image rotation. Editing paths or connecting iCloud triggers an immediate asynchronous rescan.
