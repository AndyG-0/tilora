from __future__ import annotations

import pytest

from app import config


@pytest.fixture
def dashboard_yaml(tmp_path, monkeypatch):
    path = tmp_path / "dashboard.yaml"
    path.write_text(
        """
widgets:
  - id: weather
    type: weather
    enabled: true
    layout: { col: 1, row: 1, colSpan: 1, rowSpan: 1 }
    settings: { latitude: 1, longitude: 2 }
  - id: disabled-widget
    type: weather
    enabled: false
    layout: { col: 2, row: 1, colSpan: 1, rowSpan: 1 }
    settings: {}
"""
    )
    monkeypatch.setattr(config, "DASHBOARD_CONFIG_PATH", path)
    return path


def test_load_dashboard_config_parses_widgets(dashboard_yaml):
    parsed = config.load_dashboard_config()
    ids = [w["id"] for w in parsed["widgets"]]
    assert ids == ["weather", "disabled-widget"]


def test_widget_config_returns_matching_widget(dashboard_yaml):
    widget = config.widget_config("weather")
    assert widget["type"] == "weather"
    assert widget["settings"] == {"latitude": 1, "longitude": 2}


def test_widget_config_raises_for_unknown_id(dashboard_yaml):
    with pytest.raises(KeyError):
        config.widget_config("nonexistent")


def test_effective_settings_falls_back_to_env_defaults(tmp_db):
    result = config.effective_settings()
    assert result["timezone"] == config.settings.timezone
    assert result["ai_model"] == config.settings.ai_model


def test_effective_settings_layers_db_overrides_on_top(tmp_db, monkeypatch):
    from app.storage import db

    db.save_app_settings({"timezone": "America/Chicago"})

    result = config.effective_settings()
    assert result["timezone"] == "America/Chicago"
    assert result["ai_model"] == config.settings.ai_model


def test_resolve_tabs_defaults_when_unconfigured():
    assert config.resolve_tabs({"widgets": []}) == [{"id": "default", "name": "Dashboard"}]


def test_resolve_tabs_returns_configured_tabs():
    tabs = [{"id": "home", "name": "Home"}, {"id": "media", "name": "Media"}]
    assert config.resolve_tabs({"tabs": tabs, "widgets": []}) == tabs


def test_list_widget_configs_returns_yaml_widgets_unchanged(dashboard_yaml, tmp_db):
    parsed = config.load_dashboard_config()

    widgets = config.list_widget_configs(parsed)

    ids = [w["id"] for w in widgets]
    assert ids == ["weather", "disabled-widget"]


def test_list_widget_configs_appends_custom_widgets(dashboard_yaml, tmp_db):
    from app.storage import db

    db.save_custom_widget("weather-abc123", "weather", {"col": 2, "row": 2, "colSpan": 1, "rowSpan": 1}, "media")
    parsed = config.load_dashboard_config()

    widgets = config.list_widget_configs(parsed)

    custom = next(w for w in widgets if w["id"] == "weather-abc123")
    assert custom == {
        "id": "weather-abc123",
        "type": "weather",
        "enabled": True,
        "layout": {"col": 2, "row": 2, "colSpan": 1, "rowSpan": 1},
        "settings": {},
        "tab": "media",
        "owner_user_id": None,
        "owner_device_id": None,
    }


def test_list_widget_configs_omits_tab_key_when_unset(dashboard_yaml, tmp_db):
    from app.storage import db

    db.save_custom_widget("weather-abc123", "weather", {"col": 2, "row": 2, "colSpan": 1, "rowSpan": 1}, None)
    parsed = config.load_dashboard_config()

    widgets = config.list_widget_configs(parsed)

    custom = next(w for w in widgets if w["id"] == "weather-abc123")
    assert "tab" not in custom


def test_list_widget_configs_still_includes_removed_yaml_widget(dashboard_yaml, tmp_db):
    # Existence vs. visibility split: list_widget_configs answers "does this
    # widget exist" (used to construct every Plugin instance at startup) and
    # must never filter by hidden/removed state — that's a per-(user,
    # device) concern handled only by app.api.widgets's visibility filter.
    from app.storage import db

    db.mark_widget_removed("weather")
    parsed = config.load_dashboard_config()

    widgets = config.list_widget_configs(parsed)

    assert "weather" in [w["id"] for w in widgets]


def test_list_widget_configs_still_includes_removed_custom_widget(dashboard_yaml, tmp_db):
    from app.storage import db

    db.save_custom_widget("weather-abc123", "weather", {"col": 2, "row": 2, "colSpan": 1, "rowSpan": 1}, None)
    db.mark_widget_removed("weather-abc123")
    parsed = config.load_dashboard_config()

    widgets = config.list_widget_configs(parsed)

    assert "weather-abc123" in [w["id"] for w in widgets]
