# Chores & To-Do Widget

The **Chores** widget (`type: chores`) provides a personal to-do checklist for each household member.

---

## Features

- **Personal Scope**: Items belong to the currently logged-in user profile and follow them to any device.
- **Fast Checkbox Completion**: Tap any circle checkbox to strike through and complete tasks.
- **Swipe to Delete**: Remove finished tasks effortlessly.
- **Voice Assistant Integration**: Ask *"Tilora, what chores do I have today?"* or *"Tilora, add clean gutters to my to-do list"*.

---

## Configuration (`dashboard.yaml`)

```yaml
- id: chores
  type: chores
  enabled: true
  layout: { col: 2, row: 2, colSpan: 1, rowSpan: 2 }
  settings:
    title: "To-Do"
```
