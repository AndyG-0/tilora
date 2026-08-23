# Asus Router Widget

The **Asus Router** widget (`type: asus_router`) connects to Asus routers running Asuswrt or Asuswrt-Merlin over SSH to monitor WAN connectivity, active devices, network throughput, and run port scans.

---

## Features

- **WAN & Connectivity Status**: Displays public IP address, WAN connection state, and uptime.
- **Client Device List**: Lists all currently connected Wi-Fi (2.4GHz/5GHz/6GHz) and wired Ethernet clients with IP addresses, MAC addresses, and hostnames.
- **Real-time Traffic Counters**: Displays live upstream and downstream bandwidth rates.
- **Client Modal & Port Scanning**: Tap any client device in the detail view to inspect its MAC/IP details and tap **Scan Ports** to run a quick LAN port scan discovering open web services (HTTP, HTTPS, SSH, Plex, etc.).

---

## Configuration

Credentials and connection details are configured via **Settings → Admin settings → Asus Router** or in `dashboard.yaml`:

```yaml
- id: asus_router
  type: asus_router
  enabled: true
  layout: { col: 3, row: 13, colSpan: 2, rowSpan: 1 }
  settings:
    host: "192.168.50.1"
    ssh_port: 22
    username: "admin"
```

> [!TIP]
> Tilora connects via **SSH** rather than the web admin interface because the Asus web UI only allows one concurrent admin session. Enable SSH in your router's administration settings (*Administration → System → Enable SSH*).
