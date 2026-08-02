from __future__ import annotations

from app.integrations import broadcast_links


def test_link_for_known_network():
    assert broadcast_links.link_for("ESPN") == "https://www.espn.com/watch"


def test_link_for_is_case_insensitive():
    assert broadcast_links.link_for("peacock") == broadcast_links.link_for("Peacock")


def test_link_for_strips_whitespace():
    assert broadcast_links.link_for("  ESPN  ") == "https://www.espn.com/watch"


def test_link_for_unknown_network_returns_none():
    assert broadcast_links.link_for("Regional Sports Network") is None
