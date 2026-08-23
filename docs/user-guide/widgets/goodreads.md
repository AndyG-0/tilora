# Goodreads Widget

The **Goodreads** widget (`type: goodreads`) displays your current book reading progress, book covers, author information, and reading shelves from your public Goodreads profile.

---

## Features

- **Public Shelf RSS Integration**: Connects via Goodreads public shelf feeds without requiring API keys or account credentials.
- **Shelf Selector**: View `currently-reading`, `read`, `to-read`, or any custom shelf.
- **Personal Scope**: Each household member can connect their own Goodreads account.

---

## Configuration (`dashboard.yaml`)

```yaml
- id: goodreads
  type: goodreads
  enabled: true
  layout: { col: 1, row: 15, colSpan: 1, rowSpan: 2 }
  settings:
    user_id: "12345678" # Numeric ID from your profile URL
    shelf: "currently-reading"
```
