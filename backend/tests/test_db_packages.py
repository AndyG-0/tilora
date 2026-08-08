from __future__ import annotations

from app.storage import db


def test_add_package_returns_stored_fields(tmp_db):
    package = db.add_package("packages", "1Z999AA1", "Birthday gift")

    assert package["widget_id"] == "packages"
    assert package["tracking_number"] == "1Z999AA1"
    assert package["label"] == "Birthday gift"
    assert package["carrier"] is None
    assert package["status"] is None
    assert package["last_event"] is None
    assert package["eta_date"] is None
    assert package["delivered"] is False
    assert package["updated_at"] is None
    assert isinstance(package["id"], int)


def test_add_package_defaults_label_to_none(tmp_db):
    package = db.add_package("packages", "1Z999AA1")

    assert package["label"] is None


def test_list_packages_scoped_to_widget(tmp_db):
    db.add_package("packages", "mine")
    db.add_package("other-widget", "not-mine")

    numbers = [p["tracking_number"] for p in db.list_packages("packages")]
    assert numbers == ["mine"]


def test_list_packages_orders_active_before_delivered(tmp_db):
    delivered = db.add_package("packages", "delivered-one")
    db.add_package("packages", "active-one")
    db.update_package_status(delivered["id"], delivered=True)

    numbers = [p["tracking_number"] for p in db.list_packages("packages")]
    assert numbers == ["active-one", "delivered-one"]


def test_list_packages_orders_active_by_earliest_eta_first(tmp_db):
    later = db.add_package("packages", "later")
    sooner = db.add_package("packages", "sooner")
    db.add_package("packages", "no-eta")
    db.update_package_status(later["id"], eta_date="2026-08-10")
    db.update_package_status(sooner["id"], eta_date="2026-08-07")

    numbers = [p["tracking_number"] for p in db.list_packages("packages")]
    assert numbers == ["sooner", "later", "no-eta"]


def test_get_package_returns_none_for_unknown_id(tmp_db):
    assert db.get_package(9999) is None


def test_get_package_returns_the_row(tmp_db):
    package = db.add_package("packages", "1Z999AA1")

    assert db.get_package(package["id"])["tracking_number"] == "1Z999AA1"


def test_remove_package_deletes_and_returns_row(tmp_db):
    package = db.add_package("packages", "1Z999AA1")

    removed = db.remove_package(package["id"])

    assert removed["tracking_number"] == "1Z999AA1"
    assert db.list_packages("packages") == []


def test_remove_package_returns_none_for_unknown_id(tmp_db):
    assert db.remove_package(9999) is None


def test_update_package_status_applies_all_fields(tmp_db):
    package = db.add_package("packages", "1Z999AA1")

    updated = db.update_package_status(
        package["id"],
        carrier="UPS",
        status="In Transit",
        last_event="Departed facility",
        eta_date="2026-08-10",
        delivered=False,
    )

    assert updated["carrier"] == "UPS"
    assert updated["status"] == "In Transit"
    assert updated["last_event"] == "Departed facility"
    assert updated["eta_date"] == "2026-08-10"
    assert updated["delivered"] is False
    assert updated["updated_at"] is not None


def test_update_package_status_leaves_unset_fields_unchanged(tmp_db):
    package = db.add_package("packages", "1Z999AA1")
    db.update_package_status(package["id"], carrier="UPS", status="In Transit")

    updated = db.update_package_status(package["id"], status="Out for Delivery")

    assert updated["carrier"] == "UPS"
    assert updated["status"] == "Out for Delivery"


def test_update_package_status_can_mark_delivered(tmp_db):
    package = db.add_package("packages", "1Z999AA1")

    updated = db.update_package_status(package["id"], delivered=True)

    assert updated["delivered"] is True


def test_update_package_status_returns_none_for_unknown_id(tmp_db):
    assert db.update_package_status(9999, status="whatever") is None
