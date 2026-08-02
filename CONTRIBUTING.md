# Contributing

## Dev setup

```bash
./dev.sh
```

This copies `backend/.env.example` → `backend/.env` and
`frontend/.env.example` → `frontend/.env` on first run (fill in an AI
provider key in `backend/.env` afterwards), then runs `uv sync` +
`uvicorn --reload` for the backend and `npm install` + `vite dev` for the
frontend together. Backend: http://localhost:8000. Frontend:
http://localhost:5173.

To run either side alone:

```bash
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm install && npm run dev
```

## Adding a plugin

Every widget is a `Plugin` subclass (`backend/app/plugins/base.py`):
`get_summary()` for the dashboard tile, `get_detail()` for the tap-to-drill-down
view, and an optional `get_ai_tools()` if the AI layer should be able to call
into it. `backend/app/plugins/weather/plugin.py` is the canonical example —
copy its shape for a new plugin.

To wire a new plugin in:

1. `backend/app/plugins/<name>/plugin.py` — the `Plugin` subclass. `id` must
   be unique and stable; it's used in URLs and config.
2. `backend/app/plugins/registry_types.py` — add `"<name>": YourPlugin` to
   `PLUGIN_CLASSES_BY_TYPE`.
3. `backend/config/dashboard.yaml` — add a widget entry (`id`, `type`,
   `layout`, `settings`). New widgets should ship `enabled: false` so they
   don't disturb an existing user's grid layout until they opt in and
   position them.
4. `frontend/src/lib/components/tiles/<Name>Tile.svelte` and
   `frontend/src/lib/components/details/<Name>Detail.svelte` — registered in
   the `tileComponents`/`detailComponents` maps in both
   `frontend/src/routes/+page.svelte` and
   `frontend/src/routes/widget/[id]/+page.svelte`.

If the plugin needs a user-supplied API key or OAuth client (like
`tmdb_api_key`, `discord_bot_token`, or the Google Calendar client
id/secret), follow the BYO-credentials pattern: add the field to `Settings`
and `APP_SETTINGS_KEYS` in `backend/app/config.py`, add it to `_SECRET_KEYS`
in `backend/app/api/settings.py` if it's a secret (never returned in plain
text over the API — only a `has_<key>` boolean), and add an input for it in
`frontend/src/routes/settings/+page.svelte`.

After any mutation that changes a widget's cached data, invalidate its cache
entries: `cache.delete(f"summary:{widget_id}")` /
`cache.delete(f"detail:{widget_id}")`.

## Theming

Themes are CSS-variable sets in `frontend/src/lib/themes/*.css`, selected via
`:root[data-theme='<id>']`. To add one: create the CSS file (see
`dark.css` for the variable set to define), import it in
`frontend/src/routes/+layout.svelte`, and add `{id, name}` to `_THEMES` in
`backend/app/api/theme.py`.

## Testing

**Backend** (pytest + `respx` for httpx mocking):

```bash
cd backend && uv run pytest
```

Use the `tmp_db` fixture for any test touching SQLite — it isolates a fresh
database per test. Plugin tests instantiate the plugin directly
(`Plugin({"id": ..., "settings": {...}})`) and assert on
`get_summary()`/`get_detail()`; API tests use FastAPI's `TestClient`. See
`backend/tests/test_alert_plugin.py` and `backend/tests/test_api_alerts.py`
for the shape.

**Frontend** (vitest + `@testing-library/svelte`):

```bash
cd frontend && npm run check   # svelte-check
cd frontend && npm test        # vitest run
```

Component tests live next to the component (`AlertTile.svelte` +
`AlertTile.test.ts`). Mock `$lib/api` and `$app/navigation` with
`vi.mock`/`vi.hoisted` rather than hitting the real backend — see
`frontend/src/lib/components/tiles/AlertTile.test.ts`.

CI (`.github/workflows/ci.yml`) runs both suites on every push; a PR should
pass both before merge.

## Commits / PRs

Keep commits self-contained (one plugin, one feature) and prefer a clear
"why" in the message over restating the diff. PRs should note any manual
verification done (e.g. "enabled the widget in `dashboard.yaml` and checked
the tile/detail view") alongside the automated test results, since plugin
UI rendering isn't covered by the backend suite.

## Releasing

Tilora uses plain semantic versioning (`X.Y.Z` in `VERSION`,
`backend/pyproject.toml`, and `frontend/package.json`; `vX.Y.Z` for git tags
and GitHub releases — see `backend/app/update_check.py` for why only plain
`X.Y.Z` is supported, no prerelease/build suffixes). From an up-to-date
`main` with a clean working tree:

```bash
./scripts/release.sh patch   # or: minor / major
git push origin main
git push origin vX.Y.Z       # printed by the script — triggers the release workflows
```

The script bumps `VERSION`, `backend/pyproject.toml`, and
`frontend/package.json` (regenerating `backend/uv.lock` and
`frontend/package-lock.json` in the process), then commits and tags the
release locally — it never pushes on its own (pass `--push` to do both in
one step). Pushing the tag triggers `.github/workflows/publish-images.yml`
(GHCR images) and `.github/workflows/release.yml` (the GitHub Release, with
notes auto-generated from merged PRs/commits since the last tag).

## Out of scope for now

Distributing plugins as installable third-party packages (a marketplace/plugin
store) isn't settled yet — see `TODO.md`. Until that lands, new
plugins live in-tree under `backend/app/plugins/`.
