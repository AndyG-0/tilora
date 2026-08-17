# Linux installation and Raspberry Pi kiosk setup

## Updating

### Native (systemd) installation

Run the standalone update script to pull the latest code, rebuild, and
restart the services — no interactive prompts, preserves your configuration:

```bash
bash ~/tilora/deploy/update.sh
```

Or as a one-liner without a local checkout:

```bash
curl -fsSL https://raw.githubusercontent.com/AndyG-0/tilora/main/deploy/update.sh | bash
```

You can also trigger the same update from the dashboard: **Settings → Software
update → Update now** (admin-only, native installs only).  The UI shows a
progress indicator and automatically reconnects once the services have
restarted.

### Docker

```bash
docker compose pull
docker compose up --build -d
```

---

## One-line installation

On Debian, Ubuntu, Raspberry Pi OS, or other Debian-based distributions
(Pop!_OS, Linux Mint, Armbian, DietPi, etc.), sign in as the non-root
account that should run Tilora and run:

```bash
curl -fsSL https://raw.githubusercontent.com/AndyG-0/tilora/main/deploy/install.sh | bash
```

The installer requests `sudo`, installs apt-based dependencies, checks out
`main` to `~/tilora`, builds both backend and frontend services, and enables
them at boot via systemd.

On first run, the installer interactively prompts for:
- Timezone and weather location coordinates
- Optional AI provider and API key (input is masked; `.env` is created owner-only `0600`)
- **Kiosk display configuration**: Whether to configure a local fullscreen Chromium kiosk display on this machine or install in server-only (headless) mode.

### Installation modes

1. **Server / Headless mode (connect from other devices)**:
   Installs backend and frontend services only without installing browser or GUI dependencies. Access the dashboard from any smartphone, tablet, laptop, or wall display on your local network at `http://<host-ip>:5173`.
   
   To install non-interactively or enforce server-only mode:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/AndyG-0/tilora/main/deploy/install.sh | bash -s -- --no-kiosk
   # or with environment variable
   TILORA_KIOSK=0 curl -fsSL https://raw.githubusercontent.com/AndyG-0/tilora/main/deploy/install.sh | bash
   ```

2. **Kiosk mode (dedicated touchscreen / local smart display)**:
   Installs Chromium, mouse-hiding utilities (`unclutter`), Wayland display sleep management (`wlopm`), configures microphone capture policies for voice commands without browser permission popups, and creates desktop autostart entries.
   
   To install non-interactively or enforce kiosk mode:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/AndyG-0/tilora/main/deploy/install.sh | bash -s -- --kiosk
   # or with environment variable
   TILORA_KIOSK=1 curl -fsSL https://raw.githubusercontent.com/AndyG-0/tilora/main/deploy/install.sh | bash
   ```

Rerun the installer later to fast-forward the checkout, rebuild, and restart the
services. It preserves `backend/.env`, `backend/config/dashboard.yaml`, and
the SQLite database. If you have made Git changes in `~/tilora`, the safe
fast-forward stops rather than overwriting them.

The dashboard is available locally at `http://localhost:5173`. On a trusted LAN, use
the host's IP address with port `5173` (e.g. `http://192.168.1.100:5173`). Manage services with:

```bash
sudo systemctl status tilora-backend tilora-frontend
journalctl -u tilora-backend -u tilora-frontend -f
```

The installer intentionally does not install `ffmpeg`. Add it only for the
HDHomeRun widget's `server_transcode` playback mode:

```bash
sudo apt install -y ffmpeg
```

For the `qsv`/`vaapi` hardware-acceleration presets (see `hwaccel` in
`backend/config/dashboard.yaml`), also install a VA-API driver — plain
`ffmpeg` links against the VA-API/oneVPL runtime libraries but ships no
hardware driver on its own:

```bash
sudo apt install -y va-driver-all vainfo
```

`vainfo` should then list your GPU's supported profiles instead of erroring.

The service unit is sandboxed (`NoNewPrivileges=true`, `ProtectSystem=strict`,
an empty `CapabilityBoundingSet`) and, by default, cannot open a GPU render
node: the sandbox hides `/dev/dri`, and the `tilora` service user isn't in the
host's `render` group. Both have to be granted explicitly. Add a drop-in:

```bash
sudo systemctl edit tilora-backend
```

```ini
[Service]
# Expose just the render nodes, not all of /dev.
DeviceAllow=/dev/dri/renderD128 rw
DeviceAllow=/dev/dri/renderD129 rw
SupplementaryGroups=render
```

Then `sudo systemctl restart tilora-backend`. Verify with the widget's
hardware-acceleration diagnostics (HDHomeRun widget → **Edit playback
settings** → **Run diagnostics**), which reports the process's groups, each
render node's permissions, the loaded driver, and a real test encode through
every preset. Note the render node isn't always `renderD128` — a second DRM
device shifts the iGPU to `renderD129`; the diagnostics list what's present,
and the widget's **Render device** setting selects it.

To use a non-default install location, invoke the script with `TILORA_INSTALL_DIR=/your/path`.
First installation must run from an interactive terminal (or pass pre-configured `.env` and flags)
so its setup prompts can configure initial settings.

## Manual setup

The installer is the supported path. These notes are for a manually
checked-out tree or custom service setup.

Testing `server_transcode` locally on macOS instead needs Homebrew's build:

```bash
brew install ffmpeg
```

Without it, the `/api/hdhomerun/{widget_id}/stream/{channel}` route returns a
`503` explaining that `ffmpeg` is missing, instead of transcoding. If `ffmpeg`
is installed but the tuner rejects the request (e.g. all physical tuners are
already in use by another device — HDHomeRun's `805 All Tuners In Use`), the
route returns a `502` with ffmpeg's error output in the response body instead
of a silent empty stream. The same failure is logged in full (command line,
exit code, ffmpeg output) under `app.api.hdhomerun` — `journalctl -u
tilora-backend`.

### Configure

- `backend/.env` — copy from `backend/.env.example`, set your AI provider's
  API key and `AI_MODEL`.
- `backend/config/dashboard.yaml` — copy from `dashboard.example.yaml`
  (gitignored, so it stays local to this machine), then set your real
  latitude/longitude and adjust widget layout/prompts as desired.
- `frontend/.env` — set `PUBLIC_API_BASE_URL` (usually
  `http://localhost:8000` since both services run on the same Pi).

### Build

```bash
cd backend && uv sync
cd ../frontend && npm install && npm run build
```

### Install systemd services

```bash
sed \
  -e "s|__TILORA_USER__|$USER|g" \
  -e "s|__TILORA_BACKEND_DIR__|$HOME/tilora/backend|g" \
  -e "s|__TILORA_FRONTEND_DIR__|$HOME/tilora/frontend|g" \
  deploy/tilora-backend.service | sudo tee /etc/systemd/system/tilora-backend.service >/dev/null
sed \
  -e "s|__TILORA_USER__|$USER|g" \
  -e "s|__TILORA_BACKEND_DIR__|$HOME/tilora/backend|g" \
  -e "s|__TILORA_FRONTEND_DIR__|$HOME/tilora/frontend|g" \
  deploy/tilora-frontend.service | sudo tee /etc/systemd/system/tilora-frontend.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now tilora-backend tilora-frontend
```

The backend unit is sandboxed
(`ProtectSystem=strict`) with `ReadWritePaths=` pointing at its own
directory for `storage.db` — if you relocate the checkout or set `DB_PATH`
to somewhere else, update `ReadWritePaths=` to match, or `storage.db`
writes will fail.

## Optional Raspberry Pi kiosk

For a Raspberry Pi OS desktop kiosk, install the host-side display tools:

```bash
sudo apt install -y chromium-browser unclutter wlopm
```

Enable autologin to the desktop session (`sudo raspi-config` → System
Options → Boot / Auto Login → Desktop Autologin), then add `deploy/kiosk.sh`
to labwc's autostart. Edit `~/.config/labwc/autostart` and append:

```bash
$HOME/tilora/deploy/kiosk.sh &
```

(On an X11 desktop instead of Wayland/labwc, use `~/.config/lxsession/LXDE-pi/autostart`
with an `@` prefix, and swap `wlopm` in `kiosk.sh` for `xset s off -dpms`.)

### Reboot and verify

```bash
sudo reboot
```

The Pi should boot straight into the dashboard, full-screen, with the
touchscreen able to drill into widgets. `systemctl status tilora-backend
tilora-frontend` is the first place to look if something didn't come up.

## Voice control (mic permission)

The mic button uses the browser's native `SpeechRecognition` API, which
Chromium only exposes in a secure context — satisfied here since the kiosk
points at `http://localhost:5173`/`:3000` (Chromium treats `localhost` as
secure even over plain HTTP). No extra config is needed for that part.

What does need attention on an unattended kiosk is the mic *permission*
prompt: Chromium normally asks the user to click "Allow" the first time a
page requests microphone access, but there's no one there to click it after
a fresh profile or a `--user-data-dir` reset. Pre-grant it via a Chromium
policy file instead of relying on that prompt, e.g.
`/etc/chromium/policies/managed/dashboard.json`:

```json
{
  "AudioCaptureAllowedUrls": ["http://localhost:5173", "http://localhost:3000"]
}
```

Adjust the URL(s) to match whichever port `kiosk.sh` actually points at.

## Docker (alternative to native services)

Instead of building with `uv`/`npm` and installing systemd units, you can run
both services with Docker Compose:

```bash
cp backend/.env.example backend/.env   # fill in as described above
PUBLIC_API_BASE_URL=http://<pi-ip>:8000 docker compose up --build -d
```

This replaces the backend and frontend *services* only — you still need the
optional Chromium kiosk autostart on the host, pointed at
`http://localhost:3000`.

Notes:
- `PUBLIC_API_BASE_URL` is read from the container's environment at request
  time (SvelteKit's `$env/dynamic/public`, not baked in at build time), so
  it must be an address the *browser* can reach — the Pi's LAN IP or
  `localhost` if the browser runs on the same Pi — not the in-compose
  service name (`backend`). Defaults to `http://localhost:8000` if unset,
  which is correct for the common same-Pi-kiosk setup; changing it later
  only needs `docker compose up -d` again, not a rebuild. If the frontend's
  origin differs from the backend's `CORS_ORIGIN` default
  (`http://localhost:5173`), add it there too (comma-separated for more
  than one).
- `backend/config/dashboard.yaml` and `backend/.env` are bind-mounted in, so
  edit them in place and restart the `backend` service to pick up changes.
  `storage.db` lives in a named volume (`backend-storage`) so it survives
  `docker compose down`/container recreation.
- Validated with `docker compose config` (via `podman-compose`) and a live
  `docker compose up --build` on macOS/podman: the frontend serves correctly
  end-to-end. Backend validation on that same host hit a local podman-machine
  (Apple Virtualization Framework) bug unrelated to this project — the
  `cryptography` package's Rust extension raises `SIGILL` under that specific
  hypervisor, reproducible with a bare `python:3.12-slim` image and no
  project code involved. This does not affect Docker Desktop, native Linux
  hosts, or the Raspberry Pi itself.
