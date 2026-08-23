# Shopping List Widget

The **Shopping List** widget (`type: shopping`) provides a shared household grocery and supplies checklist.

---

## Features

- **Shared Household Scope**: The list is synchronized across all family members and all screens.
- **Fast Touch Input**: Add items directly on the tile or from the detail view.
- **Check to Clear**: Tapping an item marks it as completed and removes it from the active list.
- **AI Voice Assistant Integration**: Exposes `get_shopping_list` and `add_shopping_item` to the voice assistant (e.g. *"Tilora, add bananas to the shopping list"*).

---

## Configuration (`dashboard.yaml`)

```yaml
- id: shopping
  type: shopping
  enabled: true
  layout: { col: 3, row: 2, colSpan: 1, rowSpan: 2 }
  settings:
    title: "Shopping List"
```
