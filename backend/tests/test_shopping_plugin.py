from __future__ import annotations

from app.plugins.shopping.plugin import ShoppingPlugin
from app.storage import db


def make_plugin() -> ShoppingPlugin:
    return ShoppingPlugin({"id": "shopping", "settings": {}})


async def test_get_summary_with_no_items(tmp_db):
    plugin = make_plugin()

    assert await plugin.get_summary() == {"title": "Shopping List", "items": [], "open_count": 0}


async def test_get_summary_uses_custom_title(tmp_db):
    plugin = ShoppingPlugin({"id": "shopping", "settings": {"title": "Groceries"}})

    summary = await plugin.get_summary()

    assert summary["title"] == "Groceries"


async def test_get_summary_counts_only_unchecked_items(tmp_db):
    plugin = make_plugin()
    checked = db.add_shopping_item("shopping", "Checked already", "Alice")
    db.add_shopping_item("shopping", "Still open", "Alice")
    db.check_shopping_item(checked["id"], "Bob")

    summary = await plugin.get_summary()

    assert summary["open_count"] == 1
    assert len(summary["items"]) == 2


async def test_get_summary_shows_every_households_items_regardless_of_who_added_them(tmp_db):
    plugin = make_plugin()
    db.add_shopping_item("shopping", "Alice's item", "Alice")
    db.add_shopping_item("shopping", "Bob's item", "Bob")

    summary = await plugin.get_summary()

    assert {i["text"] for i in summary["items"]} == {"Alice's item", "Bob's item"}


async def test_get_detail_matches_get_summary(tmp_db):
    plugin = make_plugin()
    db.add_shopping_item("shopping", "An item", "Alice")

    assert await plugin.get_detail() == await plugin.get_summary()
