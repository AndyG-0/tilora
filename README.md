# Tilora

[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue.svg)](https://andyg-0.github.io/tilora/)

A customizable smart-display dashboard and home server for Raspberry Pi, Debian,
Ubuntu, and other Linux devices. Run it as a dedicated fullscreen touchscreen
kiosk or as a lightweight home server accessible from any phone, tablet, or
browser on your network. Widgets are plugins; tap any tile to drill into
detail. Ships with several dozen reference plugins — Weather, an
AI-generated daily briefing, a local Photos slideshow, Movies & Shows (TMDB
popular movies and TV shows with JustWatch-sourced availability), Jellyfin,
HDHomeRun live TV, Discord, Calendar (Google/Microsoft/CalDAV), Pi-hole,
Docker/Podman container status, system monitoring, Synology, Asus router,
Steam, sports scores, RSS, and more — plus a foundation meant for adding
more. `backend/app/plugins/` (one subdirectory per plugin) is always the
authoritative list; `backend/app/plugins/registry_types.py` maps each
widget's config `type` to its plugin class.

## Stack

- **Backend:** Python (FastAPI), in-process plugin architecture, SQLite
  for AI run history and runtime settings overrides, APScheduler for
  cron-based AI prompts, a provider-agnostic AI layer (via `litellm`, with
  Anthropic/OpenAI/Gemini support) so the model is a config change, not a
  code change. AI tool-calling can pull tools from local plugins and/or
  external MCP servers (`backend/app/ai/mcp_client.py`, configured via
  `mcp_servers` in `backend/config/dashboard.yaml`).
- **Frontend:** SvelteKit, touch-first styling, CSS-variable theming
  (light/dark/sepia/high-contrast), REST polling per widget, a Settings
  page (gear icon) for AI provider keys and the dashboard's timezone.
- **Deployment:** one-line native installer for Debian-based Linux distros
  (server or kiosk mode), systemd units, and Docker Compose — see `deploy/README.md`.

## Repository layout

```
backend/    FastAPI app, plugins, AI layer, config
frontend/   SvelteKit dashboard UI
cli/        `tilora` management CLI (status/update/kiosk/config/doctor) for
            native installs — see deploy/README.md
deploy/     systemd units, kiosk launch script, Pi setup notes
VERSION     current release version, checked against GitHub releases for
            the in-app update notification (backend/app/update_check.py)
TODO.md     follow-up work (i18n, voice, drag-to-rearrange, auth, ...)
```

## Local development

**Backend:**

```bash
cd backend
cp .env.example .env   # fill in an API key for your chosen AI provider
cp config/dashboard.example.yaml config/dashboard.yaml   # your local widget config, gitignored
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

**Documentation (live reload):**

```bash
./docs.sh   # Serves documentation at http://localhost:8080
```


The frontend expects the backend at `PUBLIC_API_BASE_URL` (`frontend/.env`,
defaults to `http://localhost:8000`), and the backend allows CORS from
`CORS_ORIGIN` (`backend/.env`, defaults to `http://localhost:5173` for this
local dev setup — the Docker Compose files below set it to port 3000
themselves, since that's where they serve the frontend, comma-separated if
you need more than one origin) — keep these in sync with whatever
ports/hosts you actually run on. Both are read at runtime, not baked in at
build time, so frontend and backend can run on different devices — just
point `PUBLIC_API_BASE_URL` at wherever the backend is reachable from the
browser, and add that frontend origin to `CORS_ORIGIN`.

## Tests

```bash
cd backend && uv run pytest
cd frontend && npm run test   # add `:watch` for watch mode
```

`npm run check` (svelte-check) also runs in CI alongside both test suites —
see `.github/workflows/ci.yml`.

## Adding a plugin

See `CONTRIBUTING.md` for the step-by-step pattern, and `TODO.md` for
planned/speculative follow-up work.

## Running with Docker

**Build from source** (`docker-compose.yml`):

```bash
cp backend/.env.example backend/.env   # fill in an AI provider key
cp backend/config/dashboard.example.yaml backend/config/dashboard.yaml
PUBLIC_API_BASE_URL=http://<host-ip>:8000 CORS_ORIGIN=http://<host-ip>:3000 docker compose up --build -d
```

**Pull pre-built images** (`docker-compose.prod.yml`) — published to GHCR on
every tagged release by `.github/workflows/publish-images.yml`:

```bash
cp backend/.env.example backend/.env
cp backend/config/dashboard.example.yaml backend/config/dashboard.yaml
docker compose -f docker-compose.prod.yml up -d
```

The published frontend image reads `PUBLIC_API_BASE_URL` from the
container's environment at request time (default
`http://localhost:8000`, correct when the browser and both containers
share a host, e.g. a kiosk Pi) — no rebuild needed if your setup needs a
different backend address, just override the environment variable (see
the comments in `docker-compose.prod.yml`) and restart the container.
Both compose files already set the backend's `CORS_ORIGIN` for you
(default `http://localhost:3000`, matching the frontend service above) —
if you override `PUBLIC_API_BASE_URL` to point at a different host, set
`CORS_ORIGIN` to that same host on port 3000 alongside it, e.g.
`PUBLIC_API_BASE_URL=http://<host-ip>:8000 CORS_ORIGIN=http://<host-ip>:3000 docker compose -f docker-compose.prod.yml up -d`.

📖 **[Full Documentation & Guides](https://andyg-0.github.io/tilora/)** · **[Widget Catalog](https://andyg-0.github.io/tilora/user-guide/widgets/overview/)** · **[Admin Guide](https://andyg-0.github.io/tilora/admin-guide/overview/)** · **[Deployment](https://andyg-0.github.io/tilora/deployment/raspberry-pi-kiosk/)**

### Container widget: Docker/Podman socket access

The Docker/Podman Container widget reads container status through the host's Docker or Podman Engine API socket. Tilora supports connecting directly via Unix socket, TCP, or through a locked-down **`socket-proxy` sidecar** (`ghcr.io/tecnativa/docker-socket-proxy`) to prevent root socket exposure to the backend.

See the **[Container Host Management & Security Guide](https://andyg-0.github.io/tilora/admin-guide/container-hosts/)** for configuration steps across Docker, rootless Podman, and remote hosts.

### Hardware-accelerated live TV & transcoding

The backend container bundles `ffmpeg` and VA-API/Quick Sync drivers for real-time live TV stream transcoding (HDHomeRun MPEG-2 OTA to H.264/AAC).

- **Diagnostics**: Open HDHomeRun → *Edit playback settings* → *Run diagnostics* (admin only) to verify `/dev/dri` permissions and test hardware encoding presets.
- **Troubleshooting & Setup**: See the **[Hardware Acceleration Guide](https://andyg-0.github.io/tilora/admin-guide/hardware-acceleration/)** for `/dev/dri` passthrough, systemd permissions, and driver details (`iHD`, `i965`, `radeonsi`, `nvenc`, `videotoolbox`).

For native Debian, Ubuntu, Raspberry Pi OS, and Debian-based distro installation, run:
```bash
curl -fsSL https://raw.githubusercontent.com/AndyG-0/tilora/main/deploy/install.sh | bash
```
See **[Linux & Raspberry Pi Kiosk Setup](https://andyg-0.github.io/tilora/deployment/raspberry-pi-kiosk/)** and `deploy/README.md` for configuration, upgrades, server-only vs kiosk modes, and network options.

## Network exposure & security

Tilora requires a session-cookie login (a household profile + optional PIN) for every widget read and write. Settings follow a 4-tier model (Admin, User-level, Widget-instance, Device).

Tilora is designed to run on a trusted home / local network (LAN), not to be exposed directly to the public internet without an authenticating reverse proxy or VPN (Tailscale, WireGuard). Tilora uses a single backend process backed by SQLite WAL mode. See the **[Security Guide](https://andyg-0.github.io/tilora/admin-guide/security/)** for architecture details.

## Voice assistant & speech recognition

Tilora includes an AI voice assistant accessible via the top-bar microphone button or continuous wake-word detection (`"Tilora"`).

- **Speech Recognition (STT)**: Native Web Speech API (Chrome/Edge/Safari) or Cloud STT via OpenAI Whisper (Chromium kiosks, Firefox, Brave).
- **Text-to-Speech (TTS)**: Built-in browser voices, OpenAI Cloud TTS, or self-hosted Piper neural voices.
- **Audio Policies**: See the **[Voice Setup Guide](https://andyg-0.github.io/tilora/admin-guide/voice-setup/)** for Chromium `--autoplay-policy=no-user-gesture-required` and insecure origin permissions.


## License

MIT — see `LICENSE`.
