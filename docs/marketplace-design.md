# Plugin marketplace — design proposal

This is a design document only. Nothing here is implemented, and no
implementation timeline is committed. It exists so TODO.md's marketplace
item is a concrete, evaluable proposal instead of a one-line placeholder.
Per `CONTRIBUTING.md`'s "Out of scope for now" note, third-party plugin
distribution isn't settled, and new plugins currently live in-tree.

## 1. Motivation & non-goals

**Motivation:** Tilora ships several dozen reference plugins in-tree
(`backend/app/plugins/`), each requiring a core-repo PR to add, update, or
remove. That's fine for maintainer-authored integrations, but it means every
niche integration (a specific NAS model, a regional transit API, a hobbyist's
custom API) either has to justify inclusion in the core repo or can't exist
at all. A marketplace would let third parties publish and users install
plugins without touching the core codebase.

**Non-goals of this document:**
- Not proposing a specific launch date or committing engineering time.
- Not resolving every open question (see §13) — some tradeoffs are flagged
  as genuinely undecided rather than prematurely settled.
- Not proposing changes to any *existing* in-tree plugin's behavior; this is
  additive infrastructure.

## 2. Current architecture recap

Plugins today are **compile-time, in-process, fully-trusted Python/Svelte
code**, wired through four hardcoded, hand-maintained lists:

- **Backend registry**: `backend/app/plugins/registry_types.py`'s
  `PLUGIN_CLASSES_BY_TYPE` dict maps a `type` string to a `Plugin` subclass,
  built from ~30 explicit `from app.plugins.<name>.plugin import ...`
  statements. Every plugin type must be a compiled-in import.
- **Startup loading**: `backend/app/main.py`'s `load_plugins()` reads
  `backend/config/dashboard.yaml`, looks up each widget's `type` in that
  dict, layers settings (plugin defaults → yaml → DB overrides), and
  constructs one instance per widget into a single in-memory
  `PluginRegistry` singleton (`backend/app/plugins/base.py`).
- **Frontend component map**: `frontend/src/lib/widgetComponents.ts` is the
  single source of truth mapping a `type` string to its `TileComponent`/
  `DetailComponent`/`ScreensaverComponent` Svelte imports — all static
  `import` statements resolved at build time.
- **Scheduler wiring**: `backend/app/scheduler.py` hardcodes five
  `isinstance()` checks against imported classes (`AIInsightsPlugin`,
  `PhotosPlugin`, `SpeedtestPlugin`, `WeatherPlugin`, `PackagesPlugin`) to
  register each one's background job (AI prompt runs, photo indexing,
  speedtest runs, severe-weather polling, package-tracking refresh).

`Plugin` (`backend/app/plugins/base.py`) carries no manifest metadata beyond
class attributes used internally (`id`, `name`, `refresh_interval_seconds`,
`default_settings`, `default_layout`, `settings_scope`,
`device_overridable_settings`) — no version, author, permissions, or
dependency declaration exists anywhere. Plugins run with the same trust
level as core application code: full DB access (`app.storage.db`), full
filesystem/network access, and (via `get_ai_tools()`) the ability to expose
arbitrary callables to the AI tool-calling layer. There is no sandboxing,
no process/container isolation, and no permission gate of any kind.

The only existing enable/disable mechanism is a static `enabled: true/false`
boolean per widget in `dashboard.yaml`, set before the app starts — not a
runtime install/uninstall flow.

## 3. Plugin manifest format

A marketplace plugin needs a declarative manifest separate from its code, so
the host can reason about it (version-check, display permissions, resolve
compatibility) without importing and running arbitrary Python first.

Proposed `plugin.manifest.json` (or `.toml`, TBD) shipped at the plugin
package root:

```jsonc
{
  "id": "acme-transit",              // must be unique across installed plugins
  "name": "Acme Transit",
  "version": "1.2.0",                // semver
  "author": "Jane Doe <jane@example.com>",
  "description": "Live departure boards for Acme regional transit.",
  "host_version_range": ">=0.7.0 <2.0.0",  // compatible Tilora versions
  "widget_types": ["acme_transit"],  // one manifest may register >1 type
  "backend_entry_point": "acme_transit.plugin:AcmeTransitPlugin",
  "frontend_entry_point": "dist/widget.js",  // see §7
  "permissions": ["network:acmetransit.com", "credentials:api_key"],
  "settings_schema": { /* JSON Schema, drives a generic settings form */ },
  "default_layout": { "colSpan": 1, "rowSpan": 1 }
}
```

`settings_schema` is the key addition beyond what in-tree plugins need:
today, each plugin's settings UI is hand-built in
`frontend/src/routes/settings/+page.svelte` or the plugin's own
`<Name>Detail.svelte` edit controls. A third-party plugin can't ship a
custom Svelte settings form without also shipping frontend code (see §7),
so a JSON-Schema-driven generic settings form is the fallback every plugin
gets for free; a plugin may still supply a custom form via its frontend
bundle for anything the generic form can't express.

## 4. Discovery & distribution mechanism

Three options, not mutually exclusive:

| Approach | Pros | Cons |
|---|---|---|
| Central index (npm/PyPI-style registry) | Discoverable, supports search/ratings, natural home for a review gate | Most infrastructure to build and moderate; a v1 blocker if required |
| Git-URL install (`tilora plugin install github.com/user/repo`) | Zero new infra — reuses git; works day one | No discovery/search; a user has to already know the URL |
| Signed tarball upload via the existing admin UI | Works for local/offline installs (e.g. air-gapped kiosk setups already implied by the "kiosk deployment" work in the README) | No discovery; manual distribution burden on the author |

**Recommendation:** start with git-URL install (§14, v1) — it needs no new
hosting infrastructure and is consistent with how many self-hosted-app
ecosystems (Home Assistant HACS, Homebridge) bootstrapped before building a
central index. A central index is a v3 concern, not a prerequisite.

## 5. Backend loading mechanism

Replace `PLUGIN_CLASSES_BY_TYPE`'s static import list with dynamic,
manifest-driven loading:

1. Installed plugins live outside `backend/app/plugins/` (e.g.
   `~/.tilora/plugins/<id>/` or a configured data directory), each with its
   manifest + code.
2. At startup (and on install/uninstall, see §8), scan that directory,
   parse each manifest, and `importlib`-import each `backend_entry_point`
   into a registry keyed by `type` — functionally replacing the hardcoded
   dict with one built by directory scan + manifest parse instead of source
   edits. In-tree plugins can either be migrated to the same format or kept
   as a separate, always-present "built-in" registry merged with the
   dynamic one — the latter avoids a risky rewrite of ~30 working plugins as
   a prerequisite for shipping v1.
3. `Plugin` ABC becomes a versioned interface contract (see §9) that a
   third-party plugin's class must satisfy — the manifest's
   `host_version_range` is checked before import, so an incompatible plugin
   fails loudly at load time instead of at first request.

## 6. Sandboxing & permission model

**This is the highest-risk, least-resolved section.** Today's in-process
full trust is fine for maintainer-reviewed, in-tree code; it is not
acceptable for arbitrary third-party code with full DB/filesystem/network
access and a path into the AI tool-calling surface.

Options, roughly in increasing isolation (and increasing implementation
cost):

- **Trust-based v1 (no technical sandbox):** require plugins to declare
  `permissions` in the manifest, show them to the user before install (like
  a mobile app permission prompt), and rely on a "verified publisher"
  review process rather than a runtime enforcement boundary. Cheapest to
  ship; the security model is entirely social/review-based, which is a real
  limitation to be upfront about.
- **Capability-scoped API surface:** instead of a plugin importing
  `app.storage.db`/`httpx` directly, it receives an injected, permission-
  scoped client object (e.g. an HTTP client restricted to the hosts listed
  in its `network:` permissions, a credentials accessor limited to secrets
  it declared needing — see §11). This doesn't require process isolation
  but does require every plugin (including in-tree ones, to keep one code
  path) to stop reaching into `app.*` internals directly, which is a
  meaningful refactor of the existing `Plugin` base class contract.
- **Process isolation (subprocess/worker):** run each third-party plugin in
  its own subprocess communicating over a narrow RPC boundary (e.g. the
  `get_summary`/`get_detail`/`get_ai_tools` calls become RPC calls). Blocks
  filesystem/DB access by default; the RPC boundary itself becomes the
  permission gate. Meaningful latency/complexity cost for a dashboard that
  polls frequently.
- **WASM sandboxing:** compile plugin logic to WASM and run it in a
  restricted runtime (e.g. via `wasmtime`). Strongest isolation, but
  requires plugins to be written against a WASM-compatible toolchain — a
  significant authoring-experience cost that would likely suppress
  third-party contribution rather than enable it, at least for a Python-
  shaped plugin ecosystem.

**No recommendation is made here beyond sequencing** (see §14): ship the
trust-based model first with clear permission disclosure, and treat
capability-scoping as the natural v2 once there's a real ecosystem to
justify the refactor cost. Process/WASM isolation should only be revisited
if the trust-based model proves insufficient in practice (e.g. a malicious
or buggy plugin causes real harm) — building it preemptively for a
zero-plugin ecosystem is very likely wasted effort.

## 7. Frontend dynamic component loading

`frontend/src/lib/widgetComponents.ts`'s static `import` statements need a
dynamic-loading path for third-party components:

- Vite/Svelte support dynamic `import()` of a module at a runtime-known
  path, which can load a plugin's `frontend_entry_point` bundle (pre-built
  by the plugin author, shipped alongside the manifest) at runtime instead
  of compile time.
- `TileComponent`/`DetailComponent`/`ScreensaverComponent`'s current
  TypeScript union types (each an exhaustive `typeof X | typeof Y | ...`
  list) can't include a type unknown at compile time. These would need to
  relax to a looser structural type (e.g. a Svelte component accepting a
  known `{ widget }` prop shape) for dynamically-loaded entries, while
  in-tree plugins keep their precise types — a hybrid `Record<string,
  TileComponent | DynamicTileComponent>` rather than a wholesale type
  loosening that would lose type safety for the ~30 existing plugins.
- A generic **fallback "unknown widget" renderer** is needed for: a plugin
  installed but its bundle failed to load, a plugin whose `type` isn't in
  either the static or dynamic map (e.g. after an uninstall left a stale
  `dashboard.yaml`/DB entry), and as the default detail view driven purely
  by `settings_schema` (§3) for plugins that don't ship a custom frontend
  bundle at all — this last case is actually the *simplest* path to a
  working third-party plugin (backend-only, generic settings form, no
  custom Svelte required), worth calling out as a good v1 minimum bar.

## 8. Install/uninstall lifecycle

Proposed states: `discovered → downloading → installed → enabled ⇄ disabled
→ uninstalled`.

- **Install**: fetch (git clone / tarball download), verify (checksum,
  optionally signature — see §12), parse manifest, check
  `host_version_range` compatibility, register in the dynamic backend
  loader (§5) and frontend bundle map (§7), persist an "installed plugins"
  record (new DB table) so it survives restarts without needing
  `dashboard.yaml` edits.
- **Enable/disable**: same semantics as today's `dashboard.yaml` `enabled`
  flag, but runtime-toggleable rather than requiring a restart — this
  already has a natural home in the existing widget-settings API surface
  (`backend/app/api/widgets.py`).
- **Uninstall**: remove from the loader/bundle maps, decide what happens to
  the plugin's persisted settings/data — recommend soft-delete (retain data,
  hide the widget) rather than hard-delete by default, with a separate
  explicit "delete all data" action, since accidental uninstall shouldn't
  silently destroy a user's data (e.g. years of chore-tracking history).
- **Upgrade**: fetch new version, re-check `host_version_range`, and run
  any plugin-declared migration step (not currently modeled — would need a
  `migrate(old_version, new_version)` hook on `Plugin` if any third-party
  plugin needs to reshape its stored settings/data across versions).
- **Rollback on failed install**: if manifest parsing, compatibility check,
  or backend import fails, install should leave no partial state — nothing
  registered, nothing in the installed-plugins table — rather than leaving
  a half-wired plugin that errors on every request.

## 9. Versioning & compatibility contract

- The `Plugin` ABC itself needs a version number (e.g. `PLUGIN_API_VERSION`
  constant in `backend/app/plugins/base.py`), bumped on any breaking change
  to the abstract interface (`get_summary`/`get_detail`/`get_ai_tools`
  signatures, `Plugin.__init__` contract, `with_settings()` behavior).
- A manifest's `host_version_range` is checked against the *running app's*
  version (already tracked — `VERSION` file, per
  `CONTRIBUTING.md`'s Releasing section) at install and at every startup
  load, not just at install time, since an app upgrade could break a
  previously-compatible plugin.
- Deprecation policy: any breaking `Plugin` ABC change should be
  accompanied by a deprecation window (old + new interface supported for at
  least one minor version) once third-party plugins exist to break — this
  doesn't apply yet since there's no external ecosystem today, but should
  be adopted the moment there is one.

## 10. Scheduler integration

`backend/app/scheduler.py`'s five hardcoded `isinstance()` checks
(`schedule_ai_widgets`, `schedule_photo_index_widgets`,
`schedule_speedtest_widgets`, `schedule_severe_weather_widgets`,
`schedule_package_refresh_widgets`) don't generalize to a plugin type the
scheduler doesn't know about at compile time.

**Proposal:** add an optional `get_scheduled_jobs()` hook to `Plugin`
(mirroring the existing optional `get_ai_tools()` pattern), returning a list
of job specs (trigger type, interval/cron, handler) that the scheduler
registers generically for *every* plugin instance, in-tree or third-party:

```python
def get_scheduled_jobs(self) -> list[ScheduledJobDef]:
    """Background jobs this plugin instance needs. Optional to override."""
    return []
```

This is worth doing regardless of the marketplace timeline — it replaces
five special-cased functions with one generic dispatch loop, which is a
straightforward cleanup of existing in-tree code, not marketplace-specific
scaffolding built speculatively.

## 11. BYO-credentials interaction

Today's pattern (per `CONTRIBUTING.md`): a plugin needing a credential adds
a field to `Settings`/`APP_SETTINGS_KEYS` (`backend/app/config.py`) and
`SECRET_APP_SETTINGS_KEYS` (`backend/app/api/settings.py`) — both are
core-repo edits, not something a third-party plugin can do to itself.

**Proposal:** a manifest-declared credential schema (extending
`permissions` from §3, e.g. `"credentials": [{"key": "api_key", "secret":
true, "label": "Acme API key"}]`), stored in a plugin-scoped credentials
table (not the global `Settings` object) and injected into the plugin's
config at construction time the same way `config["settings"]` already is.
This keeps the security property `_SECRET_KEYS`/`SECRET_APP_SETTINGS_KEYS`
provides today (never returned in plaintext over the API, only a `has_<key>`
boolean) without requiring a core-repo edit per third-party plugin.

## 12. Review/signing pipeline

Start minimal, matching the trust-based v1 sandboxing stance (§6):

- **v1:** checksum verification on install (detect corruption/tampering in
  transit, not malicious intent) + mandatory display of the manifest's
  declared `permissions` before the user confirms install — informed
  consent, not enforcement.
- **v2:** an optional "verified publisher" program — manual review of
  submitted plugins by maintainers or trusted community reviewers, a badge
  shown in the (eventual) central index, no change to the unverified
  install path.
- **v3:** code-signing (author signs releases; host verifies signature
  matches a known public key on file for that plugin id) once a central
  index exists to anchor publisher identity to.

Full automated security review (static analysis, sandboxed execution
scanning) is explicitly out of scope for this document — flagged as an open
question in §13, not a v1/v2/v3 commitment.

## 13. Open questions / explicitly deferred

Being honest about what this document does *not* resolve:

- Whether process/WASM isolation (§6) is ever actually necessary, or
  whether a trust+disclosure model is sufficient long-term for a
  self-hosted single-household dashboard (a materially different threat
  model than a multi-tenant SaaS marketplace).
- Whether in-tree plugins should eventually migrate to the same
  manifest+dynamic-loading mechanism as third-party ones (one code path) or
  stay a permanently separate "built-in" registry (simpler, lower risk of
  regressing 30 working plugins).
- Payment/monetization for plugin authors — not addressed at all; assumed
  out of scope unless the user decides otherwise later.
- How much of the generic `settings_schema`-driven form (§3/§7) can realistically
  replace hand-built settings UIs like `SynologyDetail.svelte`'s
  admin-gated edit controls, versus how often a plugin will need a genuinely
  custom frontend bundle.
- Concrete choice of manifest format (JSON vs. TOML vs. Python metadata) —
  JSON was used for illustration in §3 only, not a settled decision.

## 14. Phased rollout proposal

- **v1 — trusted, git-URL install, no sandboxing:** manifest format (§3),
  git-URL install flow (§4), dynamic backend loading merged with the
  existing in-tree registry (§5), permission disclosure at install with no
  enforcement (§6 trust-based tier), generic `settings_schema`-driven
  settings form as the default (no custom frontend bundle required for a
  minimal plugin) (§7), scheduler's `get_scheduled_jobs()` hook (§10, worth
  doing independent of everything else). Small enough to validate the whole
  concept with a handful of early third-party plugins before investing
  further.
- **v2 — permission model + basic sandboxing:** capability-scoped API
  surface (§6), plugin-scoped credentials store (§11), install/uninstall
  lifecycle with soft-delete (§8), "verified publisher" review tier (§12).
- **v3 — public index + signing:** central discoverable index (§4), code
  signing anchored to publisher identity (§12), upgrade/migration hooks
  (§8), any remaining open questions from §13 revisited with real
  ecosystem data instead of speculation.

Each phase should be treated as contingent on the previous phase's actual
uptake — there is no value in building v3's signing infrastructure for a
marketplace with zero published plugins.
