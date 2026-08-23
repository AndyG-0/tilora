# Container (Docker & Podman) Widget

The **Container** widget (`type: container`) provides real-time monitoring, state inspection, and log streaming for Docker and Podman containers across multiple local or remote hosts.

---

## Features

- **Docker & Podman Support**: Connect to standard Docker Engine sockets, rootless Podman sockets, or remote TCP daemon proxies.
- **Multi-Host Management**: Switch between multiple server hosts from the detail view.
- **Container Lifecycle**: Inspect running, paused, restarting, and exited states with CPU and memory usage indicators.
- **Live Logs**: Tap any container in the detail view to view real-time log output.
- **Secure by Default**: Integrates seamlessly with `socket-proxy` sidecars to eliminate root socket exposure.

---

## Configuration

Configure host endpoints under **Settings → Admin settings → Container hosts** or in `dashboard.yaml`:

```yaml
- id: container
  type: container
  enabled: true
  layout: { col: 1, row: 11, colSpan: 2, rowSpan: 1 }
  settings:
    engine: docker # "docker" or "podman"
    connection: tcp # "tcp" or "socket"
    host: "socket-proxy"
    port: 2375
```

> [!NOTE]
> For container security best practices and `socket-proxy` setup, refer to the [Container Host Management Guide](../../admin-guide/container-hosts.md).
