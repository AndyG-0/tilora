from __future__ import annotations

from app.storage import db


def test_create_alert_returns_stored_fields(tmp_db):
    alert = db.create_alert("alert", "Freeze warning", "warning")

    assert alert["widget_id"] == "alert"
    assert alert["message"] == "Freeze warning"
    assert alert["severity"] == "warning"
    assert alert["dismissed"] is False
    assert alert["expires_at"] is None
    assert isinstance(alert["id"], int)


def test_create_alert_sets_expires_at_when_given_minutes(tmp_db):
    alert = db.create_alert("alert", "Reminder", "info", expires_in_minutes=30)

    assert alert["expires_at"] is not None
    assert alert["expires_at"] > alert["created_at"]


def test_list_active_alerts_excludes_dismissed(tmp_db):
    alert = db.create_alert("alert", "Dismiss me", "info")
    db.create_alert("alert", "Keep me", "info")

    db.dismiss_alert(alert["id"])

    messages = [a["message"] for a in db.list_active_alerts("alert")]
    assert messages == ["Keep me"]


def test_list_active_alerts_excludes_expired(tmp_db):
    db.create_alert("alert", "Already expired", "info", expires_in_minutes=-1)
    db.create_alert("alert", "Still active", "info")

    messages = [a["message"] for a in db.list_active_alerts("alert")]
    assert messages == ["Still active"]


def test_list_active_alerts_scoped_to_widget_id(tmp_db):
    db.create_alert("alert", "Mine", "info")
    db.create_alert("other-widget", "Not mine", "info")

    messages = [a["message"] for a in db.list_active_alerts("alert")]
    assert messages == ["Mine"]


def test_get_alert_returns_none_for_unknown_id(tmp_db):
    assert db.get_alert(9999) is None


def test_get_alert_returns_stored_alert(tmp_db):
    created = db.create_alert("alert", "Look here", "critical")

    fetched = db.get_alert(created["id"])

    assert fetched == created


def test_dismiss_alert_marks_as_dismissed(tmp_db):
    alert = db.create_alert("alert", "Bye", "info")

    db.dismiss_alert(alert["id"])

    assert db.get_alert(alert["id"])["dismissed"] is True
