# Dashboard Navigation & Layout

Tilora's dashboard is built with a touch-first philosophy, designed to be as fluid on a wall-mounted touchscreen as it is on a desktop or phone browser.

---

## Grid Layout & Responsive Breakpoints

The main dashboard is organized as an auto-flowing CSS grid. Layouts adapt dynamically across three viewport breakpoints:

| Breakpoint | Typical Device | Columns | Drag & Resize |
|---|---|---|---|
| **Wide** (> 1024px) | Desktop, Wall TV, Landscape Tablet | 4 columns | Supported (Drag / Resize handle) |
| **Medium** (701px – 1024px) | Portrait Tablet, Small Kiosk | 3 columns | Supported (Drag / Resize handle) |
| **Narrow** (≤ 700px) | Smartphones | 1–2 columns | Flow layout |

Layout customizations (positions and tile dimensions) are persisted per `(user, device)` pair. Changing your layout on your phone will not disturb the wall display in the kitchen.

---

## Gestures & Interactions

### Drill-Down Navigation
- **Tap or Click any Tile**: Opens the interactive detail view for that widget.
- **Back Button / Gesture**: Tap the top-left **← Back** button or swipe from the left edge to return to the main dashboard.

### Drag-to-Rearrange & Resize
- **Move**: Tap and hold (touch) or click and drag a tile's title area to reorder tiles. Surrounding tiles shift smoothly to accommodate the new position.
- **Resize**: Grab the resize indicator in the bottom-right corner of any tile to expand it across multiple grid columns or rows.

### Multi-Tab Switching
When multiple tabs are defined in your `dashboard.yaml`:
- **Touch Swipe**: Swipe left or right anywhere on the dashboard background to switch tabs.
- **Keyboard Arrows**: Press `Left Arrow` or `Right Arrow` to switch between tabs.
- **Tab Bar**: Tap directly on a tab name at the top of the dashboard.

---

## Adding and Hiding Widgets

1. Scroll to the bottom of the dashboard or open the settings menu.
2. Tap **+ Add Widget** to open the widget picker.
3. Select any available widget plugin to insert it into your grid.
4. To remove a widget, enter edit mode on the tile or tap **Remove Widget** from its detail view. Removing a widget you own deletes it; removing a default system widget hides it from your current device profile without affecting other household members.
