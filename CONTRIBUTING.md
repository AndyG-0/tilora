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
`cache.delete(f"detail:{widget_id}")` (or `_cache_key(...)` for a
`"personal"`-scope widget — see below).

### Settings tiers

Tilora is a shared household dashboard with multiple physical screens
("devices") and multiple household members ("users"), so "a setting" isn't
one thing — it lands in one of four tiers depending on *who* it belongs to
and *where* it should follow them. Getting the tier wrong is what causes bugs
like a tile one person added on the kitchen tablet showing up (or being
uneditable) on the living-room display.

1. **Admin** — one value for the whole household, controlled only by an
   admin. Examples: user management (`backend/app/api/admin.py`), app-wide
   config in `Settings`/`app_settings` (`PATCH /api/settings`, gated
   household-wide by `Depends(get_current_admin)` on the whole router —
   *nobody* non-admin can even read it), and shared service credentials in
   the `network_integrations` table (NAS/router/media-server host+creds,
   Docker/Podman socket, HDHomeRun tuner address — see
   `app.plugins.network_settings`). This tier is unrelated to
   `Plugin.settings_scope` below; it's admin-only end to end, with no
   per-user or per-device read path at all.
2. **User-level** — belongs to one household member and follows them to
   *any* device they log into. This is `Plugin.settings_scope = "personal"`
   (`backend/app/plugins/base.py`), stored per-user in
   `widget_user_settings` (or a dedicated table for data that isn't simple
   key/value settings, e.g. `user_credentials` for iCloud Apple ID/password,
   `packages.user_id` for tracked deliveries). Examples: which RSS feeds to
   follow, Steam/Goodreads account linkage, iCloud Photos login, package
   tracking numbers, 2048/Wordle high scores, AI voice selection. Any
   logged-in user can read and write their own settings; there's nothing to
   gate in the UI, since `GET .../summary|detail` already returns the
   requesting user's own data via the session cookie.
3. **Widget settings** — belongs to one widget *instance*, sourced from its
   `dashboard.yaml` entry or `custom_widgets.settings` row and keyed by
   widget id: it's the base layer every widget reads from, e.g. *which*
   subset of your user-level RSS feed catalog this particular tile displays
   is an ordinary settings key on that widget instance, not a new mechanism.
   Whether household members share this widget's value or each get their
   own is `Plugin.settings_scope: ClassVar[Literal["network", "personal"]]`
   (`backend/app/plugins/base.py`), which defaults to `"network"` (one
   shared value, e.g. a NAS/router/media-server host+credentials, stored in
   `widget_settings` or a `network_integrations` row) — this is tier 1's
   admin-only-write rule, but enforced per widget: any logged-in user can
   `GET .../summary|detail`, only an admin can `PATCH .../settings`
   (`backend/app/auth.py`'s `require_write_access` 403s a non-admin). On the
   frontend, gate the corresponding `<Name>Detail.svelte`'s edit controls
   behind `$user?.role === 'admin'` (see `SynologyDetail.svelte`) — a UX
   nicety only, since the backend enforces the real check. Setting
   `settings_scope = "personal"` instead makes this tier 2 (see above) —
   just that one class attribute; no other code changes are needed as long
   as `__init__` stays cheap and side-effect-free (true for every plugin
   today), since personalization works by constructing a fresh instance per
   request via `Plugin.with_settings()`/`scoped_plugin()` rather than
   mutating the shared registry singleton.
4. **Device** — belongs to one (user, device) *pair*, not a device alone.
   Two people sharing a screen must not see each other's layout, and one
   person's phone and tablet may reasonably differ — so this tier is keyed
   `(user_id, device_id)` throughout: `widget_layout` (position/size, keyed
   further by breakpoint), `hidden_widget_ids` (a tile hidden from just this
   pair's view), and `custom_widgets.owner_user_id`/`owner_device_id` (which
   pair created a UI-added tile — see "Tile visibility" below). A narrower
   per-device-only knob also exists for settings that depend on *this
   screen's hardware/browser* rather than who's logged in — e.g. Jellyfin's
   `playback_mode` — via `Plugin.device_overridable_settings` layered on top
   of tier 2/3, stored in `widget_device_settings` keyed by `device_id`
   alone (any user on that device shares the override, since it's a
   property of the screen, not the viewer).

**Tile visibility** (which of the above governs whether a tile even
*appears*): `dashboard.yaml` widgets are visible to everyone by default —
opt-out, via `hidden_widget_ids` — so a brand-new (user, device) pair starts
from the admin's curated dashboard rather than blank. Widgets added through
the UI are private by default — opt-in — to the (user, device) pair that
created them, via `custom_widgets.owner_user_id`/`owner_device_id`. Legacy
custom widgets predating this scheme have `NULL` owner columns and stay
visible to everyone, since there's no historical owner to attribute them to.
Deleting a widget you own fully removes it (registry, layout, settings,
photo index); deleting one you don't own just hides it for your own (user,
device) pair — see `remove_widget` in `backend/app/api/widgets.py`.

`settings_scope` is normally a fixed `ClassVar`, but it can be a `@property`
instead when a plugin's own settings determine which household members
should share a value — `PhotosPlugin` is the one example today:
`"personal"` only when `provider == "icloud_private"` (a connected Apple
ID), `"network"` for every other photo source (local folder,
`icloud_shared`, Immich), since those have nothing user-specific to
protect.

When in doubt about which tier a new setting belongs in, ask two questions:
would every household member expect the *same* answer, or their *own*
(tier 1/3 vs. tier 2)? And would someone expect the same answer on *every
screen* they use, or does it belong to *this* screen/pairing (tier 2/3 vs.
tier 4)?

## Theming

Themes are CSS-variable sets in `frontend/src/lib/themes/*.css`, selected via
`:root[data-theme='<id>']`. To add one: create the CSS file (see
`dark.css` for the variable set to define), import it in
`frontend/src/routes/+layout.svelte`, and add `{id, name}` to `_THEMES` in
`backend/app/api/theme.py`.

## Internationalization (i18n)

Supported locales are English (`en`, default/fallback), Spanish (`es`),
French (`fr`), and German (`de`).

Frontend catalogs live in `frontend/src/lib/i18n/locales/*.json` (flat
dotted keys, e.g. `weather.detail.title`), loaded by
[svelte-i18n](https://github.com/kaisermann/svelte-i18n) via
`frontend/src/lib/i18n/index.ts`. In a component, `import { _ } from
'svelte-i18n'` and replace literal text with `{$_('namespace.key')}`
(`{$_('sports.live_status', { values: { status } })}` for interpolation).
Inside `<script>` code (not markup), read the formatter with `get(_)('key')`
from `svelte/store` — see `WeatherDetail.svelte`'s error-message assignments
for the pattern.

Backend catalogs live in `backend/app/locales/*.json`, looked up via
`app.i18n.t(key, locale, **params)` (dotted-key lookup, `str.format()`
interpolation, falls back to English then to the key itself). A plugin
reads the current request's locale from `self.locale` (threaded through by
`scoped_plugin`) and passes it to `t()`; see `weather/plugin.py` and
`sports/plugin.py`. Widget REST responses are cached per-locale — the cache
key always ends with `:{locale}` — so a plugin never needs to worry about a
translated response leaking to a request in a different language.

To translate a plugin: replace its hardcoded strings with `t()` calls, add
the new keys to all four `backend/app/locales/*.json` files, and do the
matching `$_()` migration plus key additions in all four
`frontend/src/lib/i18n/locales/*.json` files for its tile/detail
components. `TODO.md` tracks which plugins/components still need this.

To add a fifth language: mirror the `en` JSON file in both locale
directories, then add the language code to `SUPPORTED_LOCALES` in
`backend/app/i18n.py`, the `register()` calls in
`frontend/src/lib/i18n/index.ts`, and the `<option>` list in the Settings
page's Language `<select>`.

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
pass both before merge. `./scripts/ci-check.sh` runs everything the
`backend` and `frontend` CI jobs run, in the same order, so you can catch a
failure locally before pushing.

## Logging

**Backend**: every module gets its own `logger = logging.getLogger(__name__)`;
root config (level, format) is set once in `app/logging_config.py`, driven by
`Settings.log_level` (default `INFO`). Log caught exceptions instead of
swallowing them — an empty `except: pass`/fallback-and-move-on block hides
real failures from anyone debugging later. Pick the level by severity:
`logger.warning(...)` (with `exc_info=True` if the traceback is useful) for a
handled-but-notable failure that degrades a widget's data, `logger.debug(...)`
for an expected/frequent internal fallback, `logger.exception(...)` for an
aborted operation where the traceback itself matters. Don't add logging to
exceptions that are already surfaced to the caller (e.g. converted straight
to an `HTTPException`) — those aren't silent.

**Frontend**: use `frontend/src/lib/logger.ts`'s `logger.debug/info/warn/error`
instead of raw `console.*`. `debug`/`info` are dev-only (`import.meta.env.DEV`);
`warn`/`error` also log in production. See `api.ts`'s request-failure throws
or `PhotoDetail.svelte`'s `saveDirectory`/`startConnect` for the pattern —
log the caught error before converting it to a UI-facing message.

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
store) isn't settled yet — see `TODO.md` and the design proposal in
[`docs/marketplace-design.md`](docs/marketplace-design.md). Until that
lands, new plugins live in-tree under `backend/app/plugins/`.
