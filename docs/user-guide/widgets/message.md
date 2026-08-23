# Message Board Widget

The **Message** widget (`type: message`) serves as an in-dashboard household sticky note and announcement board.

---

## Features

- **In-Place Editing**: Tap the tile to open the detail view and update the announcement title and body text.
- **Shared Household Scope**: Updates immediately synchronize across all household screens.
- **Custom Notes**: Ideal for Wi-Fi guest credentials, family reminders, or welcome messages.

---

## Configuration (`dashboard.yaml`)

```yaml
- id: message
  type: message
  enabled: true
  layout: { col: 1, row: 6, colSpan: 2, rowSpan: 1 }
  settings:
    title: "Household Note"
    text: "Welcome to Tilora! Tap here to edit this message."
```
