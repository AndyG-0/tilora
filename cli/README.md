# tilora-cli

Management CLI for a native (systemd) Tilora installation — service
lifecycle, config, diagnostics, and kiosk toggling from the box itself.
See `deploy/README.md` at the repo root for the full command reference.

Installed automatically by `deploy/install.sh` / `deploy/update.sh` via
`uv tool install --editable`, so the `tilora` command on a real install
always matches the checked-out code — no separate publish step.

## Local development

```bash
cd cli
uv sync
uv run tilora --help
uv run pytest
```
