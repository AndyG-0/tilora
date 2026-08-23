# NASA Astronomy Picture of the Day (APOD)

The **NASA APOD** widget (`type: nasa_apod`) brings NASA's daily Astronomy Picture of the Day to your smart display.

---

## Features

- **Daily Space Imagery**: Automatically updates daily with stunning cosmic photography, planetary observations, and deep-space telescope captures.
- **Detailed Explanations**: Tap the tile to read full scientific descriptions written by professional astronomers.
- **Ambient Screensaver Support**: Renders in full resolution as part of the ambient screensaver cycle.
- **Zero Config**: Works out of the box with NASA's shared demo API key.

---

## Configuration (`dashboard.yaml`)

```yaml
- id: nasa_apod
  type: nasa_apod
  enabled: true
  layout: { col: 1, row: 3, colSpan: 1, rowSpan: 1 }
  settings:
    title: "Astronomy Picture of the Day"
```

> [!TIP]
> For higher rate limits, you can sign up for a personal API key at [api.nasa.gov](https://api.nasa.gov) and set `NASA_API_KEY` in `backend/.env`.
