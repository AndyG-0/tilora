# Tilora

A touchscreen smart-display dashboard for a Raspberry Pi, run as a web app
in Chromium kiosk mode. Widgets are plugins; tap any tile to drill into
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
- **Deployment:** one-line native Linux installer, systemd units, and an
  optional Chromium kiosk launch script — see `deploy/README.md`.

## Repository layout

```
backend/    FastAPI app, plugins, AI layer, config
frontend/   SvelteKit dashboard UI
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

The backend image bundles `ffmpeg`, so the HDHomeRun widget's
`server_transcode` playback mode works out of the box in both compose files
above — no extra install step needed (contrast with the bare-metal installer
below, which intentionally leaves `ffmpeg` out; see `deploy/README.md`).

For native Debian, Ubuntu, and Raspberry Pi OS installation, run
`curl -fsSL https://raw.githubusercontent.com/AndyG-0/tilora/main/deploy/install.sh | bash`.
See `deploy/README.md` for configuration, upgrades, and the optional Raspberry
Pi kiosk path.

## Network exposure

Tilora requires a session-cookie login (a household profile + optional PIN)
for every widget read and write — see `CONTRIBUTING.md`'s "Settings tiers"
section for how that plays out per-widget: any logged-in member can view a
widget's data, but changing a shared/network-wide setting (NAS, router,
Docker, timezone, ...) requires the `admin` role, while personal settings
(RSS feeds, calendar picks, ...) are each member's own to change. This
protects against a device that merely shares your network, but not against
another *logged-in* household member — Tilora is still built to run on a
trusted home/local network (e.g. a Pi behind your router), not to be
exposed directly to the internet. If you need remote access, put it behind
a VPN (Tailscale, WireGuard) or an authenticating reverse proxy rather than
port-forwarding it.

## Raspberry Pi kiosk deployment

See `deploy/README.md`.

## License

MIT — see `LICENSE`.
