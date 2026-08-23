# Follow-up work

The foundation (plugin system, provider-agnostic AI layer with scheduled
prompts + tool-calling, theming, drill-down navigation, kiosk deployment,
CI, GHCR image publishing) is built, along with several dozen reference
plugins — see `backend/app/plugins/` for the current list, and
`CONTRIBUTING.md` for the step-by-step pattern for adding another one.

## Recently completed

- **Tilora Help Documentation** — Comprehensive documentation for all 34
  Tilora widgets, User Guide, and Admin Guide published via MkDocs Material
  on GitHub Pages (`https://andyg-0.github.io/tilora/`). Automated GitHub
  Pages publishing workflow (`.github/workflows/docs.yml`). Streamlined
  verbose instructions in Settings and README with direct links to
  documentation.
- **Tilora Management CLI core (`tilora`)** — `status`/`start`/`stop`/`restart`,
  `update`, `logs`, `config get`/`set`, `doctor`, and `kiosk [enable|disable|status]`
  are implemented in `cli/`, distributed via `uv tool install --editable` per
  `CONTRIBUTING.md`'s Releasing section. See item 1 below for what's still
  missing from the original design.

## Remaining, ordered by effort/dependency

(small and self-contained first, large or speculative last, rather than by
when each idea came up)

1. **Round out the Tilora Management CLI (`tilora`)** — the core lifecycle,
   kiosk, logs, and diagnostics commands are done (see "Recently completed"
   above); still missing:
   - `tilora install` — interactive wizard, headless/kiosk flags, automated prerequisite setup.
   - `tilora config edit` — only `get`/`set` exist today.
   - `tilora backup` / `tilora restore` — database and config snapshots.

2. **Create a separate marketplace** for external plugins to be published,
    with a plugin store for users to dynamically add them — the largest and
    most speculative item; depends on the plugin ecosystem maturing first.
    Design proposal written, see [`docs/marketplace-design.md`](docs/marketplace-design.md)
    for the manifest format, sandboxing/permission model, dynamic-loading,
    and install lifecycle. Implementation intentionally not started.


## Architecture & Security

(triaged from technical debt audits and prioritized by impact/risk; items
that were quick to fix have already been resolved — this is just the
remainder that needs its own dedicated session)

### Architecture, Caching & Deduplication

1. **Session-Authenticated HTTP Client Abstraction** — Factor common base-URL construction, session dataclass, cache-backed authentication, and single-retry auth handling into a shared `SessionAuthClient` or helper across `pihole_client.py`, `synology_client.py`, `qbittorrent_client.py`, and `jellyfin_client.py`. Needs its own investigation pass first — each client's retry-on-auth-failure predicate differs (401 vs a DSM `success:false` error code vs 403), and there's no `synology.py` route file left in the tree, so that plugin's current wiring needs to be understood before touching its client.
2. **UI Component Cleanup** — Eliminate duplicated checklist markup/logic between `ChoresTile`/`ShoppingTile` and `ChoresDetail`/`ShoppingDetail`.

### Infrastructure & Deployment Sandboxing

3. **Systemd Sandboxing Hardening** — Restrict `ReadWritePaths` in `deploy/tilora-backend.service` from covering the whole backend source tree to strictly the required data paths (`storage.db*`, `dashboard.yaml`, `.env`, `secret.key`, `icloud_session/`). Not a one-line change: `storage.db` runs in WAL mode, which creates `-wal`/`-shm` sibling files, so listing just `storage.db` in `ReadWritePaths` would break at first write. Doing this properly means relocating the default data directory (e.g. under `BACKEND_ROOT/data/`), touching `config.py` defaults, the install script, and upgrade docs — and verifying it needs a real systemd/Linux host.

### Concurrency & Rate-Limit Safety

4. **Artificial Analysis plugin: no lock around `_fetch()`** — `backend/app/plugins/artificial_analysis/plugin.py`'s `_fetch()` checks the DB-persisted last-fetch age and calls the upstream API when stale, but concurrent widget instances (or a widget refresh racing the scheduled AI-insights job) polling right as the 24h window expires could each independently trigger an API call — wasteful against the 100/day free-tier quota, though bounded (at most as many extra calls as there are widget instances, once a day). Fix: an `asyncio.Lock` around the refetch section — a single global lock is fine given `_GLOBAL_FETCH_KEY` is already a single shared cache row.

### Security Hardening Follow-ups

5. **`isSafeUrl` consistency gap** — Bookmarks, RSS, and Goodreads links were audited this session to guard against `javascript:`-URL self-XSS via `frontend/src/lib/url.ts`'s `isSafeUrl()`, but Sports/Movie detail views (and any other tile rendering user- or feed-supplied URLs) haven't been audited for the same gap. Needs a grep across `frontend/src/lib/components/**` for raw `href={...}` bindings on non-static URLs and applying `isSafeUrl` where missing.
6. **CLI git-ref argument injection** — The new `cli/` package's `update` command (`cli/src/tilora_cli/commands/update.py`) shells out to `git`; verify any user- or config-supplied ref string can't be used for argument injection (e.g. a ref starting with `-`) before it reaches a subprocess call. Not audited in this session's review.
