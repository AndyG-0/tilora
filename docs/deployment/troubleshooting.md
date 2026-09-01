# Troubleshooting & FAQ

Common issues, diagnostics, and solutions for Tilora installations.

---

## 1. Browser Blocks Microphone on Insecure Origins

### Symptom
When clicking the microphone button or enabling continuous listening on Chrome, Edge, or Brave over plain HTTP (`http://192.168.x.x`), speech recognition fails or permissions are blocked.

### Solution
Browsers enforce secure contexts (`https://` or `localhost`) for microphone access. If connecting over an internal HTTP IP:

1. In Chrome/Brave/Edge, navigate to:
   ```
   chrome://flags/#unsafely-treat-insecure-origin-as-secure
   ```
2. Add your Tilora origin URL (e.g. `http://192.168.1.100:5173` or `http://192.168.1.100:3000`).
3. Set to **Enabled** and relaunch the browser.
4. (Or connect via HTTPS / Tailscale).

---

## 2. HDHomeRun Live TV Returns 502 / 503

### Symptom
Tapping a channel returns `503 Service Unavailable` or `502 Bad Gateway`.

### Causes & Fixes
- **503 - Missing ffmpeg**: Install ffmpeg on the host (`sudo apt install -y ffmpeg` or `brew install ffmpeg`).
- **502 - All Tuners In Use**: All physical HDHomeRun tuners are currently recording or streaming to other household devices.
- **502 - GPU Driver / Hardware Accel Failure**: Run **HDHomeRun → Edit playback settings → Run diagnostics**. If `/dev/dri` is missing or unreadable, switch the preset to `software` or grant `render` group permissions.

---

## 3. Google OAuth "redirect_uri_mismatch"

### Symptom
When connecting Google Calendar, Google displays `Error 400: redirect_uri_mismatch`.

### Solution
Your Google Cloud Console OAuth 2.0 Web Client **Authorized redirect URIs** must match your backend URL exactly:
`http://<your-host>:8000/api/calendar/auth/callback` (or your reverse proxy URL).

---

## 4. Google OAuth "Access blocked: app has not completed verification"

### Solution
In the Google Cloud Console, navigate to *APIs & Services → OAuth consent screen → Audience*, and add the Google email address as a **Test User**.

---

## 5. Spoken Responses Stay Silent on Kiosks

### Solution
Chromium blocks audio playback until the screen is touched once. Launch Chromium with `--autoplay-policy=no-user-gesture-required` (handled by `deploy/kiosk.sh`).

---

## 6. Inspecting Backend Logs

```bash
# Systemd installations
journalctl -u tilora-backend -f

# Docker installations
docker compose logs -f backend
```

---

## 7. Changing the Log Level

### Solution
The backend's log level is controlled by `LOG_LEVEL` in `backend/.env`
(`DEBUG`, `INFO`, `WARNING`, or `ERROR` — see `backend/app/logging_config.py`).
Both native and Docker installs read the same file, so the change and the
restart step are the only things that differ:

```bash
# Native (systemd)
tilora config set LOG_LEVEL DEBUG   # or edit backend/.env directly
tilora restart                      # or: sudo systemctl restart tilora-backend

# Docker
# edit LOG_LEVEL in backend/.env, then:
docker compose restart backend      # add -f docker-compose.prod.yml for prod
```

To change the level for a Docker container only, without touching the
shared `backend/.env`, add it directly to the compose file's `backend`
service instead (same pattern `docker-compose.override.yml` uses for local
dev):

```yaml
services:
  backend:
    environment:
      - LOG_LEVEL=DEBUG
```

`DEBUG` also raises the level of normally-quiet third-party loggers
(`httpx`, `asyncssh`, `icloudpy`, `uvicorn.access`).
