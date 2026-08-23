# Clock Widget

The **Clock** widget (`type: clock`) renders a real-time, customizable clock on the dashboard with multiple distinct aesthetic faces.

---

## Features

- **Multiple Clock Faces**:
    - **Digital**: Clean, modern digital readout with seconds.
    - **Analog**: Classic circular dial with hour, minute, and sweeping second hands.
    - **Binary**: True binary matrix time display for tech enthusiasts.
    - **Word**: Typographic clock illuminating words to spell the time (e.g. *"IT IS HALF PAST TEN"*).
    - **Matrix**: Digital falling code LED matrix style.
- **Timezone Synchronization**: Automatically adheres to the household timezone configured in Settings.

---

## Configuration (`dashboard.yaml`)

```yaml
- id: clock
  type: clock
  enabled: true
  layout: { col: 4, row: 1, colSpan: 1, rowSpan: 1 }
  settings:
    style: digital # "digital", "analog", "binary", "word", or "matrix"
```
