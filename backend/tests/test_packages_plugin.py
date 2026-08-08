from __future__ import annotations

from app.config import settings
from app.plugins.packages.plugin import PackagesPlugin
from app.storage import db


def make_plugin() -> PackagesPlugin:
    return PackagesPlugin({"id": "packages", "settings": {}})


async def test_get_summary_with_no_packages(tmp_db):
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary == {
        "title": "Packages",
        "arriving_today_count": 0,
        "arriving_today": [],
        "active_count": 0,
    }


async def test_get_summary_uses_custom_title(tmp_db):
    plugin = PackagesPlugin({"id": "packages", "settings": {"title": "Deliveries"}})

    summary = await plugin.get_summary()

    assert summary["title"] == "Deliveries"


async def test_get_summary_counts_active_packages(tmp_db):
    plugin = make_plugin()
    delivered = db.add_package("packages", "delivered-one")
    db.add_package("packages", "active-one")
    db.update_package_status(delivered["id"], delivered=True)

    summary = await plugin.get_summary()

    assert summary["active_count"] == 1


async def test_get_summary_flags_packages_arriving_today(tmp_db, monkeypatch):
    monkeypatch.setattr(settings, "timezone", "UTC")
    plugin = make_plugin()
    today = plugin._today()
    package = db.add_package("packages", "today-one")
    db.update_package_status(package["id"], eta_date=today)
    other = db.add_package("packages", "later-one")
    db.update_package_status(other["id"], eta_date="2099-01-01")

    summary = await plugin.get_summary()

    assert summary["arriving_today_count"] == 1
    assert [p["tracking_number"] for p in summary["arriving_today"]] == ["today-one"]


async def test_get_summary_excludes_delivered_packages_from_arriving_today(tmp_db):
    plugin = make_plugin()
    today = plugin._today()
    package = db.add_package("packages", "delivered-today")
    db.update_package_status(package["id"], eta_date=today, delivered=True)

    summary = await plugin.get_summary()

    assert summary["arriving_today_count"] == 0


async def test_get_detail_includes_full_package_list(tmp_db):
    plugin = make_plugin()
    db.add_package("packages", "1Z999AA1", "Birthday gift")

    detail = await plugin.get_detail()

    assert detail["title"] == "Packages"
    assert len(detail["packages"]) == 1
    assert detail["packages"][0]["tracking_number"] == "1Z999AA1"
    assert detail["packages"][0]["label"] == "Birthday gift"
