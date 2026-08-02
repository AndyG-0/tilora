"""Application settings and the dashboard.yaml widget config loader."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_CONFIG_PATH = BACKEND_ROOT / "config" / "dashboard.yaml"
# Overridable via env so a Docker deployment can point it at a volume-mounted
# directory (mounting a named volume directly onto a single file isn't
# possible) — see docker-compose.yml.
DB_PATH = Path(os.environ.get("DB_PATH", str(BACKEND_ROOT / "storage.db")))
# Where icloudpy persists its trusted-session cookies for the private iCloud
# Photos provider, so a backend restart doesn't need a fresh 2FA prompt.
# Overridable via env for the same reason as DB_PATH (Docker volume mounts).
ICLOUD_SESSION_DIR = Path(os.environ.get("ICLOUD_SESSION_DIR", str(BACKEND_ROOT / "icloud_session")))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # AI provider config, passed straight through to litellm. Model strings
    # follow litellm's "<provider>/<model>" convention, e.g.
    # "anthropic/claude-sonnet-5", "openai/gpt-5", or "gemini/gemini-2.5-flash".
    ai_model: str = "anthropic/claude-sonnet-5"
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None

    # IANA timezone (e.g. "America/Chicago"), used by any widget that
    # renders the current date/time (clock, date, ...).
    timezone: str = "UTC"

    # TMDB v3 API key, used by the movies plugin (themoviedb.org/settings/api).
    tmdb_api_key: str | None = None

    # Discord bot token, used by the discord plugin (discord.com/developers/applications).
    discord_bot_token: str | None = None

    # Google Calendar OAuth client (console.cloud.google.com), used by the
    # calendar plugin. The redirect URI registered with Google must be
    # `{backend_public_url}/api/calendar/auth/callback`.
    google_calendar_client_id: str | None = None
    google_calendar_client_secret: str | None = None
    backend_public_url: str = "http://localhost:8000"

    # Microsoft 365 / Outlook Calendar OAuth app registration
    # (portal.azure.com -> Microsoft Entra ID -> App registrations), used by
    # the calendar plugin when a widget's `provider` setting is "microsoft".
    # The redirect URI registered with Microsoft must be
    # `{backend_public_url}/api/calendar/auth/microsoft/callback`.
    microsoft_calendar_client_id: str | None = None
    microsoft_calendar_client_secret: str | None = None

    # Generic CalDAV calendar (iCloud, Fastmail, Nextcloud, most self-hosted
    # servers), used by the calendar plugin when a widget's `provider` setting
    # is "caldav". No OAuth app registration needed — just a server URL and
    # an account (usually an app-specific password).
    caldav_url: str | None = None
    caldav_username: str | None = None
    caldav_password: str | None = None

    # Apple ID used by the private iCloud Photos provider (full library
    # access via icloudpy), as opposed to the icloud_shared provider, which
    # needs no credentials. Unlike caldav_password, this must be the real
    # account password — Apple doesn't support app-specific passwords for
    # this API — so treat it as more sensitive than the CalDAV credentials.
    icloud_username: str | None = None
    icloud_password: str | None = None

    # Comma-separated list of allowed browser origins for the frontend, e.g.
    # "http://localhost:5173,http://192.168.1.50:3000" — lets a kiosk and a
    # phone/desktop browser reach the same backend from different origins at
    # once, and lets frontend/backend run on different hosts without the
    # backend rejecting the frontend's actual origin.
    cors_origin: str = "http://localhost:5173"

    # "owner/repo" the update checker polls GitHub releases for
    # (app/update_check.py). Defaults to upstream; forks should override
    # this so they check their own releases instead of upstream's.
    github_repo: str = "AndyG-0/tilora"

    # Flags for the device/session cookies (app/auth.py). Default to a
    # same-host, HTTP-friendly LAN kiosk deployment (frontend/backend split
    # only by port — cookie "site" ignores port, so SameSite=Lax still
    # crosses that split). If frontend and backend are deployed on genuinely
    # different hosts, cross-site cookies require SameSite=None + Secure,
    # which in turn requires real TLS — override both once a reverse proxy
    # terminates it.
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origin.split(",") if origin.strip()]


settings = Settings()

# Global settings a user can edit at runtime from the UI (AI provider/keys,
# timezone), keyed the same as the `Settings` fields above.
APP_SETTINGS_KEYS = (
    "ai_model",
    "timezone",
    "anthropic_api_key",
    "openai_api_key",
    "gemini_api_key",
    "google_calendar_client_id",
    "google_calendar_client_secret",
    "microsoft_calendar_client_id",
    "microsoft_calendar_client_secret",
    "caldav_url",
    "caldav_username",
    "caldav_password",
    "icloud_username",
    "icloud_password",
)


def effective_settings() -> dict[str, Any]:
    """`.env`-backed defaults with runtime (DB-persisted) overrides layered on top.

    Mirrors how `load_plugins` in `main.py` layers `get_widget_settings`
    overrides onto `dashboard.yaml` — lets a key or timezone entered in the
    UI take effect without restarting the backend.
    """
    from app.storage.db import get_app_settings

    base = {key: getattr(settings, key) for key in APP_SETTINGS_KEYS}
    return {**base, **get_app_settings()}


DEFAULT_TABS: list[dict[str, Any]] = [{"id": "default", "name": "Dashboard"}]


def resolve_tabs(config: dict[str, Any]) -> list[dict[str, Any]]:
    """The configured `tabs:` list, or a single synthesized default tab.

    Pure (takes an already-loaded config) so callers that load the config
    themselves compose cleanly with tests that monkeypatch
    `load_dashboard_config`.
    """
    return config.get("tabs") or DEFAULT_TABS


class DashboardConfigError(ValueError):
    """dashboard.yaml is missing a required field or has the wrong shape.

    Raised at load time so a config typo surfaces as one clear message
    (which widget, which field) instead of a bare `KeyError`/`TypeError`
    from whichever unrelated code first touches the malformed entry.
    """


_REQUIRED_LAYOUT_KEYS = ("col", "row", "colSpan", "rowSpan")


def _validate_dashboard_config(config: Any) -> None:
    if not isinstance(config, dict):
        raise DashboardConfigError("dashboard.yaml must be a mapping at the top level")

    widgets = config.get("widgets", [])
    if not isinstance(widgets, list):
        raise DashboardConfigError("dashboard.yaml's 'widgets' key must be a list")

    seen_ids: set[str] = set()
    for i, widget in enumerate(widgets):
        if not isinstance(widget, dict):
            raise DashboardConfigError(f"dashboard.yaml widgets[{i}] must be a mapping")

        widget_id = widget.get("id")
        if not isinstance(widget_id, str) or not widget_id:
            raise DashboardConfigError(f"dashboard.yaml widgets[{i}] is missing a non-empty 'id'")
        if widget_id in seen_ids:
            raise DashboardConfigError(f"dashboard.yaml has a duplicate widget id '{widget_id}'")
        seen_ids.add(widget_id)

        if not isinstance(widget.get("type"), str) or not widget["type"]:
            raise DashboardConfigError(f"widget '{widget_id}' is missing a non-empty 'type'")

        layout = widget.get("layout")
        if not isinstance(layout, dict) or any(not isinstance(layout.get(key), int) for key in _REQUIRED_LAYOUT_KEYS):
            raise DashboardConfigError(
                f"widget '{widget_id}' has an invalid 'layout' — expected integer {', '.join(_REQUIRED_LAYOUT_KEYS)}"
            )

    tabs = config.get("tabs")
    if tabs is not None:
        if not isinstance(tabs, list):
            raise DashboardConfigError("dashboard.yaml's 'tabs' key must be a list")
        for i, tab in enumerate(tabs):
            if not isinstance(tab, dict) or not isinstance(tab.get("id"), str) or not tab["id"]:
                raise DashboardConfigError(f"dashboard.yaml tabs[{i}] is missing a non-empty 'id'")


def load_dashboard_config() -> dict[str, Any]:
    with open(DASHBOARD_CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    _validate_dashboard_config(config)
    return config


def widget_config(widget_id: str) -> dict[str, Any]:
    config = load_dashboard_config()
    for widget in config.get("widgets", []):
        if widget["id"] == widget_id:
            return widget
    raise KeyError(f"No widget configured with id '{widget_id}'")


def list_widget_configs(config: dict[str, Any]) -> list[dict[str, Any]]:
    """dashboard.yaml's `widgets:` merged with UI-added/removed widgets.

    Mirrors how `get_widget_settings`/`get_widget_layout` layer DB overrides
    onto individual YAML-defined widgets, but for the widget *list* itself —
    lets an add/remove from the UI take effect without a backend restart, in
    both `main.py:load_plugins` and `app/api/widgets.py:list_widgets`.
    """
    from app.storage.db import list_custom_widgets, removed_widget_ids

    removed = removed_widget_ids()
    widgets = [w for w in config.get("widgets", []) if w["id"] not in removed]
    for custom in list_custom_widgets():
        if custom["id"] in removed:
            continue
        entry = {
            "id": custom["id"],
            "type": custom["type"],
            "enabled": True,
            "layout": custom["layout"],
            "settings": {},
        }
        if custom["tab"] is not None:
            entry["tab"] = custom["tab"]
        widgets.append(entry)
    return widgets
