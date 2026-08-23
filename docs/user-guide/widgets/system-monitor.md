# System Monitor Widget

The **System Monitor** widget (`type: system_monitor`) displays real-time resource utilization for the host machine running the Tilora backend using `psutil`.

---

## Features

- **CPU Utilization**: Live overall CPU percentage and load average indicators.
- **Memory (RAM)**: Used and available physical memory with percentage bar.
- **Disk Storage**: Root filesystem usage and available gigabytes.
- **Network I/O**: Real-time incoming and outgoing network transfer throughput.
- **Zero Config**: Gathers metrics directly from the host operating system without any external accounts or credentials.

---

## Configuration (`dashboard.yaml`)

```yaml
- id: system-monitor
  type: system_monitor
  enabled: true
  layout: { col: 4, row: 2, colSpan: 1, rowSpan: 1 }
  settings: {}
```
