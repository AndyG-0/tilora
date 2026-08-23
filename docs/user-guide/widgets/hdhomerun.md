# HDHomeRun Live TV Widget

The **HDHomeRun** widget (`type: hdhomerun`) connects to SiliconDust HDHomeRun network TV tuners for live over-the-air television streaming, program guide (EPG) grids, and DVR recording status.

---

## Features

- **Live In-Browser TV Playback**: Uses server-side `ffmpeg` transcoding (H.264/AAC via HLS or MPEG-TS) to play raw MPEG-2 broadcast streams seamlessly across all modern browsers.
- **Hardware Acceleration**: Full support for hardware-accelerated transcoding on Intel Quick Sync (QSV), Linux VA-API, NVIDIA NVENC, and Apple VideoToolbox.
- **Electronic Program Guide (EPG)**: Supports SiliconDust guide data or custom XMLTV EPG URLs with interactive timeline navigation.
- **DVR Integration**: Displays upcoming recording timers and recorded episodes from an HDHomeRun DVR recording engine.
- **In-App Diagnostics**: Run hardware acceleration benchmarks and tuner diagnostics directly from the detail view.

---

## Configuration

Configure connection endpoints under **Settings → Admin settings → HDHomeRun** or in `dashboard.yaml`:

```yaml
- id: hdhomerun
  type: hdhomerun
  enabled: true
  layout: { col: 2, row: 10, colSpan: 2, rowSpan: 1 }
  settings:
    tuner_host: "192.168.1.20"
    tuner_port: 80
    dvr_host: "192.168.1.21" # Optional
    dvr_port: 59090
    epg_url: "http://example.com/guide.xml" # Optional XMLTV guide URL
    playback_mode: server_transcode # "server_transcode" or "external"
    hwaccel: vaapi # "software", "vaapi", "qsv", "nvenc", or "videotoolbox"
```

> [!NOTE]
> For GPU hardware passthrough and driver troubleshooting, see the [Hardware Acceleration Guide](../../admin-guide/hardware-acceleration.md).
