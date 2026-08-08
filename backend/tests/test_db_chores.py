from __future__ import annotations

from app.storage import db


def test_add_chore_returns_stored_fields(tmp_db):
    chore = db.add_chore("chores", "user-1", "Take out trash")

    assert chore["widget_id"] == "chores"
    assert chore["user_id"] == "user-1"
    assert chore["text"] == "Take out trash"
    assert chore["completed"] is False
    assert chore["completed_at"] is None
    assert isinstance(chore["id"], int)


def test_list_chores_scoped_to_widget_and_user(tmp_db):
    db.add_chore("chores", "user-1", "Mine")
    db.add_chore("chores", "user-2", "Not mine")
    db.add_chore("other-widget", "user-1", "Also not mine")

    texts = [c["text"] for c in db.list_chores("chores", "user-1")]
    assert texts == ["Mine"]


def test_list_chores_orders_open_before_completed(tmp_db):
    first = db.add_chore("chores", "user-1", "First")
    db.add_chore("chores", "user-1", "Second")
    db.complete_chore(first["id"], "user-1")

    texts = [c["text"] for c in db.list_chores("chores", "user-1")]
    assert texts == ["Second", "First"]


def test_complete_chore_marks_done_and_sets_completed_at(tmp_db):
    chore = db.add_chore("chores", "user-1", "Do it")

    completed = db.complete_chore(chore["id"], "user-1")

    assert completed["completed"] is True
    assert completed["completed_at"] is not None


def test_complete_chore_returns_none_for_wrong_user(tmp_db):
    chore = db.add_chore("chores", "user-1", "Mine")

    assert db.complete_chore(chore["id"], "user-2") is None


def test_complete_chore_returns_none_for_unknown_id(tmp_db):
    assert db.complete_chore(9999, "user-1") is None


def test_remove_chore_deletes_and_returns_row(tmp_db):
    chore = db.add_chore("chores", "user-1", "Bye")

    removed = db.remove_chore(chore["id"], "user-1")

    assert removed["text"] == "Bye"
    assert db.list_chores("chores", "user-1") == []


def test_remove_chore_returns_none_for_wrong_user(tmp_db):
    chore = db.add_chore("chores", "user-1", "Mine")

    assert db.remove_chore(chore["id"], "user-2") is None
    assert len(db.list_chores("chores", "user-1")) == 1
