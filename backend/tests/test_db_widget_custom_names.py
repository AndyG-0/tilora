from __future__ import annotations

from app.storage import db


def test_list_widget_custom_names_empty_by_default(tmp_db):
    assert db.list_widget_custom_names() == {}


def test_save_then_list_widget_custom_name_round_trips(tmp_db):
    db.save_widget_custom_name("weather", "Home")

    assert db.list_widget_custom_names() == {"weather": "Home"}


def test_save_widget_custom_name_overwrites_prior_value(tmp_db):
    db.save_widget_custom_name("weather", "Home")
    db.save_widget_custom_name("weather", "Work")

    assert db.list_widget_custom_names() == {"weather": "Work"}


def test_clear_widget_custom_name_removes_it(tmp_db):
    db.save_widget_custom_name("weather", "Home")
    db.clear_widget_custom_name("weather")

    assert db.list_widget_custom_names() == {}


def test_clear_widget_custom_name_is_a_noop_when_absent(tmp_db):
    db.clear_widget_custom_name("weather")

    assert db.list_widget_custom_names() == {}
