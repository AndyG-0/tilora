from __future__ import annotations

import pytest

from app.integrations import icloud_photos, icloud_shared_album, immich_client
from app.plugins.photos.indexer import index_photos
from app.plugins.photos.plugin import PhotosPlugin
from app.storage import db


def make_plugin(tmp_path, **settings) -> PhotosPlugin:
    return PhotosPlugin({"id": "photos", "settings": {"directory": str(tmp_path), **settings}})


def make_icloud_plugin(**settings) -> PhotosPlugin:
    return PhotosPlugin({"id": "photos", "settings": {"provider": "icloud_shared", "album_token": "tok", **settings}})


def make_private_plugin(**settings) -> PhotosPlugin:
    return PhotosPlugin({"id": "photos", "settings": {"provider": "icloud_private", **settings}})


def make_immich_plugin(**settings) -> PhotosPlugin:
    return PhotosPlugin(
        {
            "id": "photos",
            "settings": {
                "provider": "immich",
                "base_url": "http://192.168.1.50:2283/api",
                "api_key": "immich-key",
                "album_id": "album-1",
                **settings,
            },
        }
    )


async def _index(plugin: PhotosPlugin) -> None:
    await index_photos(plugin)


async def test_get_summary_with_empty_directory_reports_no_photos(tmp_db, tmp_path):
    plugin = make_plugin(tmp_path)
    await _index(plugin)

    summary = await plugin.get_summary()

    assert summary == {"provider": "local", "configured": True, "count": 0, "current": None}


async def test_get_summary_reports_indexing_before_first_scan_completes(tmp_db, tmp_path):
    plugin = make_plugin(tmp_path)

    summary = await plugin.get_summary()

    assert summary == {"provider": "local", "configured": True, "count": 0, "current": None, "indexing": True}


async def test_get_detail_reports_indexing_before_first_scan_completes(tmp_db, tmp_path):
    plugin = make_plugin(tmp_path)

    detail = await plugin.get_detail()

    assert detail["configured"] is True
    assert detail["indexing"] is True
    assert detail["photos"] == []


async def test_get_summary_reports_not_configured_when_directory_unset(tmp_db):
    plugin = PhotosPlugin({"id": "photos", "settings": {"provider": "local"}})

    summary = await plugin.get_summary()

    assert summary == {"provider": "local", "configured": False, "count": 0, "current": None}
    assert "indexing" not in summary


async def test_get_detail_reports_not_configured_when_directory_unset(tmp_db):
    plugin = PhotosPlugin({"id": "photos", "settings": {"provider": "local"}})

    detail = await plugin.get_detail()

    assert detail["configured"] is False
    assert "indexing" not in detail
    assert detail["photos"] == []


async def test_get_summary_reports_index_error_after_a_failed_scan(tmp_db, tmp_path):
    plugin = make_plugin(tmp_path)
    db.mark_photo_index_scan_failed(plugin.id, "could not reach the source")

    summary = await plugin.get_summary()

    assert summary == {
        "provider": "local",
        "configured": True,
        "count": 0,
        "current": None,
        "index_error": "could not reach the source",
    }


async def test_get_summary_omits_indexing_fields_once_photos_are_indexed(tmp_db, tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"fake")
    plugin = make_plugin(tmp_path)
    await _index(plugin)

    summary = await plugin.get_summary()

    assert "indexing" not in summary
    assert "index_error" not in summary


async def test_get_summary_ignores_missing_directory(tmp_db, tmp_path):
    plugin = make_plugin(tmp_path / "does-not-exist")
    await _index(plugin)

    summary = await plugin.get_summary()

    assert summary == {"provider": "local", "configured": True, "count": 0, "current": None}


async def test_get_summary_only_counts_image_files(tmp_db, tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"fake")
    (tmp_path / "b.png").write_bytes(b"fake")
    (tmp_path / "notes.txt").write_text("not a photo")
    plugin = make_plugin(tmp_path)
    await _index(plugin)

    summary = await plugin.get_summary()

    assert summary["count"] == 2


async def test_get_summary_current_photo_has_url_under_plugin_id(tmp_db, tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"fake")
    plugin = make_plugin(tmp_path)
    await _index(plugin)

    summary = await plugin.get_summary()

    assert summary["current"] == {"filename": "a.jpg", "url": "/api/photos/photos/a.jpg"}


async def test_get_detail_lists_all_photos_sorted(tmp_db, tmp_path):
    (tmp_path / "b.jpg").write_bytes(b"fake")
    (tmp_path / "a.jpg").write_bytes(b"fake")
    plugin = make_plugin(tmp_path, interval_seconds=15)
    await _index(plugin)

    detail = await plugin.get_detail()

    assert detail["count"] == 2
    assert detail["interval_seconds"] == 15
    assert [p["filename"] for p in detail["photos"]] == ["a.jpg", "b.jpg"]


async def test_get_detail_ignores_subdirectories_by_default(tmp_db, tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"fake")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.jpg").write_bytes(b"fake")
    plugin = make_plugin(tmp_path)
    await _index(plugin)

    detail = await plugin.get_detail()

    assert [p["filename"] for p in detail["photos"]] == ["a.jpg"]


async def test_get_detail_recursive_includes_nested_photos(tmp_db, tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"fake")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.jpg").write_bytes(b"fake")
    plugin = make_plugin(tmp_path, recursive=True)
    await _index(plugin)

    detail = await plugin.get_detail()

    assert [p["filename"] for p in detail["photos"]] == ["a.jpg", "sub/nested.jpg"]
    nested = next(p for p in detail["photos"] if p["filename"] == "sub/nested.jpg")
    assert nested["url"] == "/api/photos/photos/sub/nested.jpg"


async def test_reads_do_not_trigger_a_rescan(tmp_db, tmp_path):
    """get_detail/get_summary are cheap index reads — only calling
    index_photos again picks up files added after the last scan."""
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "a.jpg").write_bytes(b"fake")
    plugin = make_plugin(tmp_path, recursive=True)

    await _index(plugin)
    first = await plugin.get_detail()
    (sub / "b.jpg").write_bytes(b"fake")
    second = await plugin.get_detail()

    assert first["count"] == 1
    assert second["count"] == 1

    await _index(plugin)
    third = await plugin.get_detail()

    assert third["count"] == 2


async def test_index_refresh_seconds_defaults_to_one_hour_and_floors_at_60(tmp_path):
    plugin = make_plugin(tmp_path)
    assert plugin.index_refresh_seconds == 3600

    floored = make_plugin(tmp_path, index_refresh_seconds=10)
    assert floored.index_refresh_seconds == 60

    custom = make_plugin(tmp_path, index_refresh_seconds=120)
    assert custom.index_refresh_seconds == 120


async def test_get_summary_and_get_detail_never_enumerate_the_live_source(tmp_db, tmp_path, monkeypatch):
    """Regression: get_summary/get_detail must only ever read the persisted
    index (db.photo_index_photo_ids), never call _enumerate_photo_ids_chunks
    themselves — that's the background job's job."""
    plugin = make_plugin(tmp_path)

    async def boom():
        raise AssertionError("get_summary/get_detail must not enumerate the live source")
        yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(plugin, "_enumerate_photo_ids_chunks", boom)

    generation = db.begin_photo_index_scan(plugin.id)
    db.upsert_photo_index_chunk(plugin.id, generation, ["a.jpg"], 0)
    db.finish_photo_index_scan(plugin.id, generation)

    summary = await plugin.get_summary()
    detail = await plugin.get_detail()

    assert summary["count"] == 1
    assert detail["count"] == 1


async def test_enumerate_photo_ids_chunks_local_yields_sorted_ids_in_one_chunk(tmp_path):
    (tmp_path / "b.jpg").write_bytes(b"fake")
    (tmp_path / "a.jpg").write_bytes(b"fake")
    plugin = make_plugin(tmp_path)

    chunks = [chunk async for chunk in plugin._enumerate_photo_ids_chunks()]

    assert chunks == [["a.jpg", "b.jpg"]]


async def test_enumerate_photo_ids_chunks_local_empty_directory_yields_nothing(tmp_path):
    plugin = make_plugin(tmp_path)

    chunks = [chunk async for chunk in plugin._enumerate_photo_ids_chunks()]

    assert chunks == []


async def test_icloud_provider_get_summary_uses_shared_album_photo_guids(tmp_db, monkeypatch):
    async def fake_fetch_photos(token):
        assert token == "tok"
        return [{"guid": "guid-1", "checksum": "chk-1", "width": 100, "height": 100}]

    monkeypatch.setattr(icloud_shared_album, "fetch_photos", fake_fetch_photos)
    plugin = make_icloud_plugin()
    await _index(plugin)

    summary = await plugin.get_summary()

    assert summary["count"] == 1
    assert summary["current"] == {"filename": "guid-1", "url": "/api/photos/photos/guid-1"}


async def test_icloud_provider_parses_token_from_full_share_url(tmp_db, monkeypatch):
    seen_tokens = []

    async def fake_fetch_photos(token):
        seen_tokens.append(token)
        return []

    monkeypatch.setattr(icloud_shared_album, "fetch_photos", fake_fetch_photos)
    plugin = make_icloud_plugin(album_token="https://www.icloud.com/sharedalbum/#tok")
    await _index(plugin)

    assert seen_tokens == ["tok"]


async def test_icloud_provider_with_no_album_token_reports_not_configured(tmp_db):
    plugin = PhotosPlugin({"id": "photos", "settings": {"provider": "icloud_shared"}})
    await _index(plugin)

    summary = await plugin.get_summary()

    assert summary == {"provider": "icloud_shared", "configured": False, "count": 0, "current": None}
    assert "indexing" not in summary


async def test_icloud_provider_get_detail_lists_all_photos(tmp_db, monkeypatch):
    async def fake_fetch_photos(token):
        return [
            {"guid": "guid-1", "checksum": "chk-1", "width": 100, "height": 100},
            {"guid": "guid-2", "checksum": "chk-2", "width": 100, "height": 100},
        ]

    monkeypatch.setattr(icloud_shared_album, "fetch_photos", fake_fetch_photos)
    plugin = make_icloud_plugin(interval_seconds=15)
    await _index(plugin)

    detail = await plugin.get_detail()

    assert detail["count"] == 2
    assert detail["interval_seconds"] == 15
    assert [p["filename"] for p in detail["photos"]] == ["guid-1", "guid-2"]


async def test_enumerate_photo_ids_chunks_icloud_shared_yields_one_chunk(monkeypatch):
    async def fake_fetch_photos(token):
        return [{"guid": "guid-1", "checksum": "chk-1"}, {"guid": "guid-2", "checksum": "chk-2"}]

    monkeypatch.setattr(icloud_shared_album, "fetch_photos", fake_fetch_photos)
    plugin = make_icloud_plugin()

    chunks = [chunk async for chunk in plugin._enumerate_photo_ids_chunks()]

    assert chunks == [["guid-1", "guid-2"]]


async def test_private_provider_with_no_credentials_reports_not_configured_and_disconnected(tmp_db):
    plugin = make_private_plugin()
    await _index(plugin)

    summary = await plugin.get_summary()

    assert summary == {
        "provider": "icloud_private",
        "configured": False,
        "count": 0,
        "current": None,
        "connected": False,
    }
    assert "indexing" not in summary


async def test_private_provider_with_credentials_but_disconnected_reports_not_indexing(tmp_db):
    user_id = _make_admin_with_icloud_credentials()
    plugin = make_private_plugin().with_settings(user_id=user_id)

    summary = await plugin.get_summary()

    assert summary["configured"] is True
    assert summary["connected"] is False
    assert "indexing" not in summary


async def test_private_provider_connected_before_first_scan_reports_indexing(tmp_db, monkeypatch):
    user_id = _make_admin_with_icloud_credentials()
    monkeypatch.setattr(icloud_photos, "is_connected_cached", lambda uid: True)
    plugin = make_private_plugin().with_settings(user_id=user_id)

    summary = await plugin.get_summary()

    assert summary["configured"] is True
    assert summary["connected"] is True
    assert summary["indexing"] is True


def _make_admin_with_icloud_credentials(username="user@example.com", password="hunter2") -> str:
    # index_photos on an unscoped plugin (no requesting_user_id — how the
    # background scheduler always calls it) fans out into one scan per user
    # with saved iCloud credentials (see app.plugins.photos.indexer), so
    # exercising the icloud_private path means seeding a real user +
    # credentials rather than monkeypatching the old global
    # settings.icloud_username/password fields (removed in favor of per-user
    # `user_credentials`). get_summary/get_detail must then be read from a
    # clone scoped to that same user (`plugin.with_settings(user_id=...)`),
    # matching how a real request is scoped via app.plugins.scoping.
    db.create_user("admin", "Admin", None, None, None, None, "2020-01-01T00:00:00Z", role="admin")
    db.save_user_credentials("admin", "icloud", {"username": username, "password": password})
    return "admin"


async def test_private_provider_get_summary_uses_configured_album(tmp_db, monkeypatch):
    user_id = _make_admin_with_icloud_credentials()

    async def fake_iter_photo_chunks(user_id, username, password, album_name):
        assert (user_id, username, password, album_name) == ("admin", "user@example.com", "hunter2", "All Photos")
        yield [{"id": "id-1", "filename": "photo.jpg"}]

    monkeypatch.setattr(icloud_photos, "iter_photo_chunks", fake_iter_photo_chunks)
    plugin = make_private_plugin()
    await _index(plugin)

    summary = await plugin.with_settings(user_id=user_id).get_summary()

    assert summary["count"] == 1
    assert summary["current"] == {"filename": "id-1", "url": "/api/photos/photos/id-1"}
    assert summary["connected"] is False


async def test_private_provider_reflects_connected_status(tmp_db, monkeypatch):
    user_id = _make_admin_with_icloud_credentials()

    async def fake_iter_photo_chunks(*a, **k):
        return
        yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(icloud_photos, "iter_photo_chunks", fake_iter_photo_chunks)
    monkeypatch.setattr(icloud_photos, "is_connected_cached", lambda user_id: True)
    plugin = make_private_plugin()
    await _index(plugin)

    summary = await plugin.with_settings(user_id=user_id).get_summary()

    assert summary["connected"] is True


async def test_private_provider_uses_custom_album_name(tmp_db, monkeypatch):
    _make_admin_with_icloud_credentials()
    seen_albums = []

    async def fake_iter_photo_chunks(user_id, username, password, album_name):
        seen_albums.append(album_name)
        return
        yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(icloud_photos, "iter_photo_chunks", fake_iter_photo_chunks)
    plugin = make_private_plugin(album_name="Family")
    await _index(plugin)

    assert seen_albums == ["Family"]


async def test_private_provider_get_detail_lists_all_photos(tmp_db, monkeypatch):
    user_id = _make_admin_with_icloud_credentials()

    async def fake_iter_photo_chunks(user_id, username, password, album_name):
        yield [{"id": "id-1", "filename": "a.jpg"}, {"id": "id-2", "filename": "b.jpg"}]

    monkeypatch.setattr(icloud_photos, "iter_photo_chunks", fake_iter_photo_chunks)
    plugin = make_private_plugin(interval_seconds=15)
    await _index(plugin)

    detail = await plugin.with_settings(user_id=user_id).get_detail()

    assert detail["count"] == 2
    assert detail["interval_seconds"] == 15
    assert [p["filename"] for p in detail["photos"]] == ["id-1", "id-2"]
    assert "connected" in detail


async def test_enumerate_photo_ids_chunks_icloud_private_yields_multiple_chunks(tmp_db, monkeypatch):
    user_id = _make_admin_with_icloud_credentials()

    async def fake_iter_photo_chunks(user_id, username, password, album_name):
        yield [{"id": "id-1", "filename": "a.jpg"}]
        yield [{"id": "id-2", "filename": "b.jpg"}, {"id": "id-3", "filename": "c.jpg"}]

    monkeypatch.setattr(icloud_photos, "iter_photo_chunks", fake_iter_photo_chunks)
    # _enumerate_photo_ids_chunks only enumerates on an instance scoped to a
    # specific connected user (see PhotosPlugin), matching how a live
    # per-viewer request is scoped via app.plugins.scoping.scoped_plugin.
    plugin = make_private_plugin().with_settings(user_id=user_id)

    chunks = [chunk async for chunk in plugin._enumerate_photo_ids_chunks()]

    assert chunks == [["id-1"], ["id-2", "id-3"]]


async def test_enumerate_photo_ids_chunks_icloud_private_without_credentials_yields_nothing(tmp_db):
    plugin = make_private_plugin()

    chunks = [chunk async for chunk in plugin._enumerate_photo_ids_chunks()]

    assert chunks == []


async def test_immich_provider_get_summary_uses_configured_album(tmp_db, monkeypatch):
    async def fake_iter_album_asset_chunks(base_url, api_key, album_id):
        assert base_url == "http://192.168.1.50:2283/api"
        assert api_key == "immich-key"
        assert album_id == "album-1"
        yield [{"id": "asset-1", "filename": "a.jpg", "width": 100, "height": 100}]

    monkeypatch.setattr(immich_client, "iter_album_asset_chunks", fake_iter_album_asset_chunks)
    plugin = make_immich_plugin()
    await _index(plugin)

    summary = await plugin.get_summary()

    assert summary["count"] == 1
    assert summary["current"] == {"filename": "asset-1", "url": "/api/photos/photos/asset-1"}
    # get_summary stays provider-agnostic beyond icloud_private's "connected"
    # flag — no immich-specific keys belong here.
    assert "immich_base_url" not in summary


async def test_immich_provider_normalizes_base_url_trailing_slash(tmp_db, monkeypatch):
    seen_base_urls = []

    async def fake_iter_album_asset_chunks(base_url, api_key, album_id):
        seen_base_urls.append(base_url)
        return
        yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(immich_client, "iter_album_asset_chunks", fake_iter_album_asset_chunks)
    plugin = make_immich_plugin(base_url="http://192.168.1.50:2283/api/")
    await _index(plugin)

    assert seen_base_urls == ["http://192.168.1.50:2283/api"]


async def test_immich_provider_with_incomplete_settings_reports_not_configured(tmp_db):
    plugin = PhotosPlugin({"id": "photos", "settings": {"provider": "immich", "base_url": "http://host/api"}})
    await _index(plugin)

    summary = await plugin.get_summary()

    assert summary == {"provider": "immich", "configured": False, "count": 0, "current": None}
    assert "indexing" not in summary


async def test_immich_provider_get_detail_lists_all_photos_and_masks_api_key(tmp_db, monkeypatch):
    async def fake_iter_album_asset_chunks(base_url, api_key, album_id):
        yield [
            {"id": "asset-1", "filename": "a.jpg", "width": 100, "height": 100},
            {"id": "asset-2", "filename": "b.jpg", "width": 100, "height": 100},
        ]

    monkeypatch.setattr(immich_client, "iter_album_asset_chunks", fake_iter_album_asset_chunks)
    plugin = make_immich_plugin(interval_seconds=15)
    await _index(plugin)

    detail = await plugin.get_detail()

    assert detail["count"] == 2
    assert detail["interval_seconds"] == 15
    assert [p["filename"] for p in detail["photos"]] == ["asset-1", "asset-2"]
    assert detail["immich_base_url"] == "http://192.168.1.50:2283/api"
    assert detail["immich_album_id"] == "album-1"
    assert detail["has_immich_api_key"] is True
    assert "api_key" not in detail
    assert "immich-key" not in str(detail)


async def test_immich_provider_get_detail_reports_no_api_key_when_unset(tmp_db):
    plugin = PhotosPlugin(
        {
            "id": "photos",
            "settings": {"provider": "immich", "base_url": "http://host/api", "album_id": "album-1"},
        }
    )
    await _index(plugin)

    detail = await plugin.get_detail()

    assert detail["has_immich_api_key"] is False


async def test_enumerate_photo_ids_chunks_immich_yields_multiple_chunks(monkeypatch):
    async def fake_iter_album_asset_chunks(base_url, api_key, album_id):
        yield [{"id": "asset-1", "filename": "a.jpg", "width": 1, "height": 1}]
        yield [
            {"id": "asset-2", "filename": "b.jpg", "width": 1, "height": 1},
            {"id": "asset-3", "filename": "c.jpg", "width": 1, "height": 1},
        ]

    monkeypatch.setattr(immich_client, "iter_album_asset_chunks", fake_iter_album_asset_chunks)
    plugin = make_immich_plugin()

    chunks = [chunk async for chunk in plugin._enumerate_photo_ids_chunks()]

    assert chunks == [["asset-1"], ["asset-2", "asset-3"]]


async def test_enumerate_photo_ids_chunks_immich_without_settings_yields_nothing():
    plugin = PhotosPlugin({"id": "photos", "settings": {"provider": "immich"}})

    chunks = [chunk async for chunk in plugin._enumerate_photo_ids_chunks()]

    assert chunks == []


async def test_enumerate_photo_ids_chunks_immich_propagates_client_errors(monkeypatch):
    async def fake_iter_album_asset_chunks(base_url, api_key, album_id):
        raise immich_client.ImmichError("could not reach the server")
        yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(immich_client, "iter_album_asset_chunks", fake_iter_album_asset_chunks)
    plugin = make_immich_plugin()

    with pytest.raises(immich_client.ImmichError):
        async for _ in plugin._enumerate_photo_ids_chunks():
            pass
