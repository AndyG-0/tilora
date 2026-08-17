from __future__ import annotations

from typing import Any, ClassVar

from app.plugins.base import Plugin
from app.plugins.scoping import scoped_plugin


class NetworkPlugin(Plugin):
    id = "network_fake"
    name = "Network Fake"

    async def get_summary(self) -> dict[str, Any]:
        return {}

    async def get_detail(self) -> dict[str, Any]:
        return {}


class PersonalPlugin(Plugin):
    id = "personal_fake"
    name = "Personal Fake"
    settings_scope: ClassVar[str] = "personal"

    async def get_summary(self) -> dict[str, Any]:
        return {}

    async def get_detail(self) -> dict[str, Any]:
        return {}


USER = {"id": "user-1"}
DEVICE = {"id": "device-1"}


async def test_network_plugin_same_locale_returns_same_instance(tmp_db):
    plugin = NetworkPlugin({"settings": {}})

    resolved = await scoped_plugin(plugin, USER, DEVICE, locale="en")

    assert resolved is plugin


async def test_network_plugin_different_locale_clones_with_new_locale(tmp_db):
    plugin = NetworkPlugin({"settings": {}})

    resolved = await scoped_plugin(plugin, USER, DEVICE, locale="es")

    assert resolved is not plugin
    assert resolved.locale == "es"
    assert plugin.locale == "en"


async def test_personal_plugin_always_clones_and_carries_locale(tmp_db):
    plugin = PersonalPlugin({"settings": {}})

    resolved = await scoped_plugin(plugin, USER, DEVICE, locale="fr")

    assert resolved is not plugin
    assert resolved.locale == "fr"


async def test_personal_plugin_clone_carries_requesting_users_id(tmp_db):
    plugin = PersonalPlugin({"settings": {}})

    resolved = await scoped_plugin(plugin, USER, DEVICE)

    assert resolved.requesting_user_id == "user-1"
    assert plugin.requesting_user_id is None


async def test_network_plugin_clone_does_not_carry_a_user_id(tmp_db):
    plugin = NetworkPlugin({"settings": {}})

    resolved = await scoped_plugin(plugin, USER, DEVICE, locale="es")

    assert resolved.requesting_user_id is None


async def test_default_locale_argument_is_english(tmp_db):
    plugin = NetworkPlugin({"settings": {}})

    resolved = await scoped_plugin(plugin, USER, DEVICE)

    assert resolved is plugin
    assert resolved.locale == "en"


async def test_photos_plugin_does_not_read_stale_widget_user_settings(tmp_db):
    from app.plugins.photos.plugin import PhotosPlugin
    from app.storage import db

    plugin = PhotosPlugin({"id": "photos", "settings": {"provider": "icloud_private"}})
    db.save_widget_user_settings(USER["id"], "photos", {"provider": "local", "directory": "/some/path"})

    resolved = await scoped_plugin(plugin, USER, DEVICE)

    assert resolved.provider == "icloud_private"
    assert resolved.requesting_user_id == USER["id"]
