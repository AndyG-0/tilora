from __future__ import annotations

from app.i18n import t


def test_known_key_resolves_in_requested_locale():
    assert t("weather.condition.clear_sky", "es") == "Cielo despejado"


def test_missing_locale_falls_back_to_english():
    assert t("weather.condition.clear_sky", "xx") == t("weather.condition.clear_sky", "en")


def test_missing_key_falls_back_to_key_itself():
    assert t("weather.condition.does_not_exist", "en") == "weather.condition.does_not_exist"


def test_interpolates_params():
    assert t("sports.error.unsupported_league", "en", league="xfl") == "Unsupported league 'xfl'."


def test_interpolates_params_in_other_locales():
    assert t("sports.error.unsupported_league", "es", league="xfl") == "Liga no compatible: 'xfl'."
