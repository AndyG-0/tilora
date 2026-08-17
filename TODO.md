# Follow-up work

The foundation (plugin system, provider-agnostic AI layer with scheduled
prompts + tool-calling, theming, drill-down navigation, kiosk deployment,
CI, GHCR image publishing) is built, along with several dozen reference
plugins — see `backend/app/plugins/` for the current list, and
`CONTRIBUTING.md` for the step-by-step pattern for adding another one.

## Remaining, ordered by effort/dependency

(small and self-contained first, large or speculative last, rather than by
when each idea came up)

1. **Tilora Management CLI (`tilora`)** — A unified command-line tool to streamline
   installation, upgrades, backups, service management, diagnostics, and
   configuration:
   - **Lifecycle commands:** `tilora install` (interactive wizard, headless/kiosk flags, automated prerequisite setup), `tilora update` (fast-forward, migrations, rebuild, zero-downtime service restart), `tilora restart`, `tilora start`, `tilora stop`, `tilora status`.
   - **Kiosk management:** `tilora kiosk [enable|disable|status]` (toggle Chromium autostart, display blanking/sleep policies, audio permissions).
   - **Configuration & Maintenance:** `tilora config [get|set|edit]` (safely inspect/modify `dashboard.yaml` and `.env`), `tilora logs` (live journalctl stream filtering backend, frontend, or errors), `tilora backup` / `tilora restore` (database and config snapshots).
   - **Diagnostics:** `tilora doctor` (checks system requirements, GPU/hwaccel DRM render nodes, port availability, network connectivity, speech permissions).
   - **Distribution:** Standalone CLI entrypoint or Python CLI package via `uv tool install tilora` / pipx / deb package.

2. **Create a separate marketplace** for external plugins to be published,
    with a plugin store for users to dynamically add them — the largest and
    most speculative item; depends on the plugin ecosystem maturing first.
    Design proposal written, see [`docs/marketplace-design.md`](docs/marketplace-design.md)
    for the manifest format, sandboxing/permission model, dynamic-loading,
    and install lifecycle. Implementation intentionally not started.
