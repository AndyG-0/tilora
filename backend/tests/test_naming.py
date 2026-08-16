from __future__ import annotations

from app.plugins.bookmarks.plugin import BookmarksPlugin
from app.plugins.container.plugin import ContainerPlugin
from app.plugins.naming import display_names
from app.plugins.sports.plugin import SportsPlugin
from app.plugins.weather.plugin import WeatherPlugin
from app.storage import db


def test_display_names_uses_location_name_when_present(tmp_db):
    plugin = WeatherPlugin({"id": "weather", "settings": {"location_name": "Chicago, IL"}})

    assert display_names([plugin]) == {"weather": "Weather (Chicago, IL)"}


def test_display_names_uses_network_integration_name(tmp_db):
    db.save_network_integration("nas-1", "container", "Docker Host", {})
    plugin = ContainerPlugin({"id": "container-a", "settings": {"network_integration_id": "nas-1"}})

    assert display_names([plugin]) == {"container-a": "Container (Docker Host)"}


def test_display_names_uses_title_when_customized(tmp_db):
    plugin = BookmarksPlugin({"id": "bookmarks", "settings": {"title": "Recipes"}})

    assert display_names([plugin]) == {"bookmarks": "Bookmarks (Recipes)"}


def test_display_names_ignores_title_matching_type_name(tmp_db):
    plugin = BookmarksPlugin({"id": "bookmarks", "settings": {"title": "Bookmarks"}})

    assert display_names([plugin]) == {"bookmarks": "Bookmarks"}


def test_display_names_falls_back_to_bare_type_name(tmp_db):
    plugin = SportsPlugin({"id": "sports", "settings": {}})

    assert display_names([plugin]) == {"sports": "Sports Schedule"}


def test_display_names_explicit_override_wins_over_everything(tmp_db):
    plugin = WeatherPlugin({"id": "weather", "settings": {"location_name": "Chicago, IL"}})
    db.save_widget_custom_name("weather", "Home")

    assert display_names([plugin]) == {"weather": "Home"}


def test_display_names_appends_stable_id_sorted_suffix_on_collision(tmp_db):
    a = SportsPlugin({"id": "sports-b", "settings": {}})
    b = SportsPlugin({"id": "sports-a", "settings": {}})
    c = SportsPlugin({"id": "sports-c", "settings": {}})

    result = display_names([a, b, c])

    assert result == {
        "sports-a": "Sports Schedule",
        "sports-b": "Sports Schedule (2)",
        "sports-c": "Sports Schedule (3)",
    }


def test_display_names_suffix_is_stable_regardless_of_input_order(tmp_db):
    a = SportsPlugin({"id": "sports-b", "settings": {}})
    b = SportsPlugin({"id": "sports-a", "settings": {}})

    forward = display_names([a, b])
    reversed_order = display_names([b, a])

    assert (
        forward
        == reversed_order
        == {
            "sports-a": "Sports Schedule",
            "sports-b": "Sports Schedule (2)",
        }
    )


def test_display_names_no_suffix_when_labels_differ(tmp_db):
    a = WeatherPlugin({"id": "weather-a", "settings": {"location_name": "Chicago, IL"}})
    b = WeatherPlugin({"id": "weather-b", "settings": {"location_name": "London, UK"}})

    assert display_names([a, b]) == {
        "weather-a": "Weather (Chicago, IL)",
        "weather-b": "Weather (London, UK)",
    }
