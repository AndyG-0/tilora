from __future__ import annotations

from app.storage import db


def test_add_shopping_item_returns_stored_fields(tmp_db):
    item = db.add_shopping_item("shopping", "Milk", "Alice")

    assert item["widget_id"] == "shopping"
    assert item["text"] == "Milk"
    assert item["checked"] is False
    assert item["added_by"] == "Alice"
    assert item["checked_by"] is None
    assert item["checked_at"] is None
    assert isinstance(item["id"], int)


def test_list_shopping_items_scoped_to_widget(tmp_db):
    db.add_shopping_item("shopping", "Mine", "Alice")
    db.add_shopping_item("other-widget", "Not mine", "Alice")

    texts = [i["text"] for i in db.list_shopping_items("shopping")]
    assert texts == ["Mine"]


def test_list_shopping_items_orders_unchecked_before_checked(tmp_db):
    first = db.add_shopping_item("shopping", "First", "Alice")
    db.add_shopping_item("shopping", "Second", "Alice")
    db.check_shopping_item(first["id"], "Bob")

    texts = [i["text"] for i in db.list_shopping_items("shopping")]
    assert texts == ["Second", "First"]


def test_check_shopping_item_marks_checked_and_sets_checked_by(tmp_db):
    item = db.add_shopping_item("shopping", "Eggs", "Alice")

    checked = db.check_shopping_item(item["id"], "Bob")

    assert checked["checked"] is True
    assert checked["checked_by"] == "Bob"
    assert checked["checked_at"] is not None


def test_check_shopping_item_returns_none_for_unknown_id(tmp_db):
    assert db.check_shopping_item(9999, "Bob") is None


def test_remove_shopping_item_deletes_and_returns_row(tmp_db):
    item = db.add_shopping_item("shopping", "Bread", "Alice")

    removed = db.remove_shopping_item(item["id"])

    assert removed["text"] == "Bread"
    assert db.list_shopping_items("shopping") == []


def test_remove_shopping_item_returns_none_for_unknown_id(tmp_db):
    assert db.remove_shopping_item(9999) is None
