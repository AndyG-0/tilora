# Date Widget

The **Date** widget (`type: date`) renders the current day of the week, calendar date, month, and year with localized formatting.

---

## Features

- **Localized Formats**: Automatically matches the user's selected language (English, Spanish, French, German).
- **Timezone Aware**: Displays current calendar date in the configured dashboard timezone.

---

## Configuration (`dashboard.yaml`)

```yaml
- id: date
  type: date
  enabled: true
  layout: { col: 1, row: 2, colSpan: 1, rowSpan: 1 }
  settings: {}
```
