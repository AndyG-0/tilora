# Hardware Acceleration & GPU Transcoding

Tilora uses `ffmpeg` for live stream transcoding (e.g. converting HDHomeRun MPEG-2 OTA streams to H.264/AAC for in-browser playback). On low-power hardware or multi-viewer households, GPU hardware acceleration dramatically reduces CPU usage.

---

## Supported Hardware Acceleration Presets

| Preset | Platform / Hardware | Backend Requirements |
|---|---|---|
| `software` | Any CPU (x86 / ARM) | Standard `ffmpeg` build (Default fallback). |
| `software_lowpower` | Raspberry Pi CPU / Low-power ARM | Uses `ultrafast` x264 preset for minimal latency. |
| `vaapi` | Linux (Intel / AMD GPU) | Mesa / Intel Media Driver (`va-driver-all`), `/dev/dri` access. |
| `qsv` | Linux (Intel Quick Sync) | Intel Gen8+ Core / N-series, `intel-media-va-driver-non-free`. |
| `nvenc` | Linux / Windows (NVIDIA GPU) | NVIDIA proprietary driver + CUDA / NVENC runtime. |
| `videotoolbox` | macOS (Apple Silicon / Intel Mac) | Native Apple VideoToolbox framework. |

---

## Linux Host Permissions & Systemd Sandboxing

By default, systemd sandboxing blocks access to GPU render nodes. To grant Tilora access:

1. Add the `tilora` user to the `render` and `video` groups:
   ```bash
   sudo usermod -aG render,video $USER
   ```
2. Add device pass-through drop-ins:
   ```bash
   sudo systemctl edit tilora-backend
   ```
   ```ini
   [Service]
   DeviceAllow=/dev/dri/renderD128 rw
   DeviceAllow=/dev/dri/renderD129 rw
   SupplementaryGroups=render video
   ```
3. Restart the service:
   ```bash
   sudo systemctl restart tilora-backend
   ```

---

## Docker GPU Passthrough

In `docker-compose.yml`, uncomment the device block under `tilora-backend`:

```yaml
services:
  backend:
    devices:
      - /dev/dri:/dev/dri
    group_add:
      - "107" # Host render group GID (`getent group render`)
```

---

## In-App Hardware Diagnostics

To test your configuration:
1. Open the HDHomeRun widget detail view.
2. Tap **Edit playback settings** → **Run diagnostics**.
3. Tilora checks `/dev/dri` nodes, permissions, loaded VA-API drivers, and performs a live test encode across every preset, identifying any misconfigurations automatically.
