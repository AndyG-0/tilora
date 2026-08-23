# Package Tracking Widget

The **Packages** widget (`type: packages`) tracks multi-carrier parcel deliveries using the 17Track API.

---

## Features

- **Multi-Carrier Tracking**: Supports FedEx, UPS, USPS, DHL, Amazon, Canada Post, Royal Mail, and 1,500+ global carriers.
- **Estimated Delivery Dates**: Displays remaining days countdown and scheduled delivery windows.
- **Shared Household List**: Add tracking numbers with friendly labels (e.g. *"Birthday Gift"* or *"New Keyboard"*) from the detail view.

---

## Configuration (`dashboard.yaml`)

```yaml
- id: packages
  type: packages
  enabled: true
  layout: { col: 3, row: 15, colSpan: 1, rowSpan: 2 }
  settings:
    title: "Packages"
```

---

## Requirements

Requires a free API key from [17track.net/en/api](https://17track.net/en/api) configured as `TRACK17_API_KEY` in `backend/.env`.
