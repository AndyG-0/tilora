# Linux Services & Systemd Sandboxing

Tilora runs natively as two hardened systemd units: `tilora-backend.service` and `tilora-frontend.service`.

---

## Service Units Overview

### Backend Unit (`/etc/systemd/system/tilora-backend.service`)

The backend service executes Python via `uvicorn` with security sandboxing enabled:

```ini
[Unit]
Description=Tilora Dashboard Backend
After=network.target

[Service]
Type=simple
User=__TILORA_USER__
WorkingDirectory=__TILORA_BACKEND_DIR__
ExecStart=/usr/local/bin/uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

# Sandboxing
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=__TILORA_BACKEND_DIR__
CapabilityBoundingSet=

[Install]
WantedBy=multi-user.target
```

### Frontend Unit (`/etc/systemd/system/tilora-frontend.service`)

The frontend service serves the built SvelteKit Node.js application:

```ini
[Unit]
Description=Tilora Dashboard Frontend
After=network.target tilora-backend.service

[Service]
Type=simple
User=__TILORA_USER__
WorkingDirectory=__TILORA_FRONTEND_DIR__
Environment=PORT=5173
Environment=PUBLIC_API_BASE_URL=__TILORA_PUBLIC_API_BASE_URL__
ExecStart=/usr/bin/node build/index.js
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

---

## Service Management Commands

```bash
# Start services
sudo systemctl start tilora-backend tilora-frontend

# Enable on boot
sudo systemctl enable tilora-backend tilora-frontend

# View live logs
journalctl -u tilora-backend -u tilora-frontend -f
```
