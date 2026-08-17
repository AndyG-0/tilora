from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import photos
from app.auth import get_current_user
from app.integrations import icloud_photos, icloud_shared_album, immich_client
from app.plugins.base import registry
from app.plugins.photos.plugin import PhotosPlugin
from app.storage import db


def register_plugin(**settings) -> PhotosPlugin:
    """Registers a photos widget the same way the live registry does (see
    `app.main.load_plugins`), so `photos.py`'s `_get_plugin` resolves it —
    mirrors `register_plugin` in test_api_pihole.py/test_api_jellyfin.py.
    """
    plugin = PhotosPlugin({"id": "photos", "settings": {**PhotosPlugin.default_settings, **settings}})
    registry.register(plugin)
    return plugin


@pytest.fixture
def client(tmp_db):
    app = FastAPI()
    app.include_router(photos.router)
    # These tests exercise photo serving, not auth — stub out who's asking
    # rather than juggling real device/session cookies here.
    app.dependency_overrides[get_current_user] = lambda: {"id": "user", "role": "member"}
    return TestClient(app)


def test_photos_routes_require_a_session(tmp_db):
    app = FastAPI()
    app.include_router(photos.router)
    client = TestClient(app)

    assert client.get("/api/photos/photos/a.jpg").status_code == 401


@pytest.fixture
def photos_dir(tmp_path):
    directory = tmp_path / "photos"
    directory.mkdir()
    (directory / "a.jpg").write_bytes(b"fake-jpeg-bytes")
    (directory / "notes.txt").write_text("not a photo")

    register_plugin(directory=str(directory))
    return directory


def test_get_photo_returns_file_bytes(client, photos_dir):
    response = client.get("/api/photos/photos/a.jpg")

    assert response.status_code == 200
    assert response.content == b"fake-jpeg-bytes"


def test_get_photo_404s_for_unknown_widget(client, photos_dir):
    response = client.get("/api/photos/nonexistent/a.jpg")

    assert response.status_code == 404


def test_get_photo_404s_for_non_image_file(client, photos_dir):
    response = client.get("/api/photos/photos/notes.txt")

    assert response.status_code == 404


def test_get_photo_404s_for_missing_file(client, photos_dir):
    response = client.get("/api/photos/photos/missing.jpg")

    assert response.status_code == 404


def test_get_photo_rejects_path_traversal(client, photos_dir):
    response = client.get("/api/photos/photos/..%2F..%2Fsecret.jpg")

    assert response.status_code in (404, 400)


@pytest.fixture
def nested_photos_dir(tmp_path):
    directory = tmp_path / "photos"
    directory.mkdir()
    (directory / "a.jpg").write_bytes(b"fake-jpeg-bytes")
    sub = directory / "sub"
    sub.mkdir()
    (sub / "nested.jpg").write_bytes(b"nested-jpeg-bytes")

    register_plugin(directory=str(directory), recursive=True)
    return directory


def test_get_photo_serves_nested_file(client, nested_photos_dir):
    response = client.get("/api/photos/photos/sub/nested.jpg")

    assert response.status_code == 200
    assert response.content == b"nested-jpeg-bytes"


def test_get_photo_rejects_traversal_via_nested_path(client, nested_photos_dir):
    response = client.get("/api/photos/photos/sub/..%2F..%2Fsecret.jpg")

    assert response.status_code in (404, 400)


@pytest.fixture
def icloud_widget():
    register_plugin(provider="icloud_shared", album_token="tok")


def test_get_photo_redirects_to_icloud_asset_url(client, icloud_widget, monkeypatch):
    async def fake_fetch_photos(token):
        assert token == "tok"
        return [{"guid": "guid-1", "checksum": "chk-1", "width": 100, "height": 100}]

    async def fake_fetch_asset_url(token, guid, checksum):
        assert (token, guid, checksum) == ("tok", "guid-1", "chk-1")
        return "https://cvws.icloud-content.com/B/abc"

    monkeypatch.setattr(icloud_shared_album, "fetch_photos", fake_fetch_photos)
    monkeypatch.setattr(icloud_shared_album, "fetch_asset_url", fake_fetch_asset_url)

    response = client.get("/api/photos/photos/guid-1", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "https://cvws.icloud-content.com/B/abc"


def test_get_photo_404s_for_unknown_icloud_guid(client, icloud_widget, monkeypatch):
    async def fake_fetch_photos(token):
        return []

    monkeypatch.setattr(icloud_shared_album, "fetch_photos", fake_fetch_photos)

    response = client.get("/api/photos/photos/missing-guid")

    assert response.status_code == 404


def test_get_photo_404s_when_icloud_shared_fetch_photos_raises(client, icloud_widget, monkeypatch):
    async def fake_fetch_photos(token):
        raise RuntimeError("shared album connection error")

    monkeypatch.setattr(icloud_shared_album, "fetch_photos", fake_fetch_photos)

    response = client.get("/api/photos/photos/guid-1")

    assert response.status_code == 404


def test_get_photo_404s_when_icloud_shared_fetch_asset_url_raises(client, icloud_widget, monkeypatch):
    async def fake_fetch_photos(token):
        return [{"guid": "guid-1", "checksum": "chk-1", "width": 100, "height": 100}]

    async def fake_fetch_asset_url(token, guid, checksum):
        raise RuntimeError("asset url fetch failed")

    monkeypatch.setattr(icloud_shared_album, "fetch_photos", fake_fetch_photos)
    monkeypatch.setattr(icloud_shared_album, "fetch_asset_url", fake_fetch_asset_url)

    response = client.get("/api/photos/photos/guid-1")

    assert response.status_code == 404


@pytest.fixture
def icloud_private_widget():
    # Photo bytes are fetched with the *requesting viewer's own* credentials
    # (see app.api.photos._get_icloud_private_photo) — each household
    # member's private library is independent, so this seeds credentials for
    # "user", the id the `client` fixture's get_current_user override stubs.
    register_plugin(provider="icloud_private", album_name="Family")
    db.create_user("user", "User", None, None, None, None, "2020-01-01T00:00:00Z", role="member")
    db.save_user_credentials("user", "icloud", {"username": "user@example.com", "password": "hunter2"})


def test_get_photo_proxies_private_photo_bytes(client, icloud_private_widget, monkeypatch):
    async def fake_fetch_photo_bytes(user_id, username, password, photo_id, album_name):
        assert (user_id, username, password, photo_id, album_name) == (
            "user",
            "user@example.com",
            "hunter2",
            "id-1",
            "Family",
        )
        return b"private-jpeg-bytes", "image/jpeg"

    monkeypatch.setattr(icloud_photos, "fetch_photo_bytes", fake_fetch_photo_bytes)

    response = client.get("/api/photos/photos/id-1")

    assert response.status_code == 200
    assert response.content == b"private-jpeg-bytes"
    assert response.headers["content-type"] == "image/jpeg"


def test_get_photo_404s_for_unknown_private_photo_id(client, icloud_private_widget, monkeypatch):
    async def fake_fetch_photo_bytes(user_id, username, password, photo_id, album_name):
        return None

    monkeypatch.setattr(icloud_photos, "fetch_photo_bytes", fake_fetch_photo_bytes)

    response = client.get("/api/photos/photos/missing-id")

    assert response.status_code == 404


def test_get_photo_404s_when_private_fetch_photo_bytes_raises(client, icloud_private_widget, monkeypatch):
    async def fake_fetch_photo_bytes(user_id, username, password, photo_id, album_name):
        raise RuntimeError("iCloud API error")

    monkeypatch.setattr(icloud_photos, "fetch_photo_bytes", fake_fetch_photo_bytes)

    response = client.get("/api/photos/photos/id-1")

    assert response.status_code == 404


def test_get_photo_404s_when_private_provider_not_configured(client, tmp_db):
    register_plugin(provider="icloud_private")

    response = client.get("/api/photos/photos/id-1")

    assert response.status_code == 404


@pytest.fixture
def immich_widget():
    register_plugin(
        provider="immich",
        base_url="http://192.168.1.50:2283/api",
        api_key="immich-key",
        album_id="album-1",
    )


def test_get_photo_proxies_immich_asset_bytes(client, immich_widget, monkeypatch):
    async def fake_fetch_asset_bytes(base_url, api_key, asset_id, size="preview"):
        assert (base_url, api_key, asset_id) == ("http://192.168.1.50:2283/api", "immich-key", "asset-1")
        return b"immich-jpeg-bytes", "image/jpeg"

    monkeypatch.setattr(immich_client, "fetch_asset_bytes", fake_fetch_asset_bytes)

    response = client.get("/api/photos/photos/asset-1")

    assert response.status_code == 200
    assert response.content == b"immich-jpeg-bytes"
    assert response.headers["content-type"] == "image/jpeg"


def test_get_photo_normalizes_immich_base_url_trailing_slash(client, monkeypatch):
    register_plugin(
        provider="immich",
        base_url="http://192.168.1.50:2283/api/",
        api_key="immich-key",
        album_id="album-1",
    )

    seen_base_urls = []

    async def fake_fetch_asset_bytes(base_url, api_key, asset_id, size="preview"):
        seen_base_urls.append(base_url)
        return b"bytes", "image/jpeg"

    monkeypatch.setattr(immich_client, "fetch_asset_bytes", fake_fetch_asset_bytes)

    client.get("/api/photos/photos/asset-1")

    assert seen_base_urls == ["http://192.168.1.50:2283/api"]


def test_get_photo_404s_for_unknown_immich_asset(client, immich_widget, monkeypatch):
    async def fake_fetch_asset_bytes(base_url, api_key, asset_id, size="preview"):
        return None

    monkeypatch.setattr(immich_client, "fetch_asset_bytes", fake_fetch_asset_bytes)

    response = client.get("/api/photos/photos/missing-asset")

    assert response.status_code == 404


def test_get_photo_404s_when_immich_client_raises(client, immich_widget, monkeypatch):
    async def fake_fetch_asset_bytes(base_url, api_key, asset_id, size="preview"):
        raise immich_client.ImmichError("could not reach the Immich server")

    monkeypatch.setattr(immich_client, "fetch_asset_bytes", fake_fetch_asset_bytes)

    response = client.get("/api/photos/photos/asset-1")

    assert response.status_code == 404


def test_get_photo_404s_when_immich_provider_not_configured(client):
    register_plugin(provider="immich", base_url="http://192.168.1.50:2283/api")

    response = client.get("/api/photos/photos/asset-1")

    assert response.status_code == 404
