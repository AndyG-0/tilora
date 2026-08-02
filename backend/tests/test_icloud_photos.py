from __future__ import annotations

from icloudpy.exceptions import ICloudPyFailedLoginException

from app.integrations import icloud_photos
from app.storage.cache import cache


class FakeResponse:
    def __init__(self, content: bytes, content_type: str = "image/jpeg"):
        self.content = content
        self.headers = {"content-type": content_type}


class FakeAsset:
    def __init__(self, id_: str, filename: str, content: bytes = b"bytes"):
        self.id = id_
        self.filename = filename
        self._content = content

    def download(self, version: str = "original"):
        return FakeResponse(self._content)


class FakeAlbum:
    def __init__(self, assets: list[FakeAsset], chunks: list[list[FakeAsset]] | None = None):
        self.photos = assets
        self._chunks = chunks if chunks is not None else ([assets] if assets else [])

    def iter_chunks(self, chunk_size: int):
        yield from self._chunks


class FakePhotosService:
    def __init__(self, albums: dict[str, FakeAlbum]):
        self.albums = albums


class FakeService:
    def __init__(self, requires_2fa: bool = False, albums: dict[str, FakeAlbum] | None = None):
        self.requires_2fa = requires_2fa
        self.is_trusted_session = False
        self.photos = FakePhotosService(albums or {})
        self._2fa_valid_code = "123456"
        self.trust_session_called = False

    def validate_2fa_code(self, code: str) -> bool:
        return code == self._2fa_valid_code

    def trust_session(self) -> None:
        self.trust_session_called = True
        self.is_trusted_session = True


def test_is_configured():
    assert icloud_photos.is_configured("user@example.com", "hunter2") is True
    assert icloud_photos.is_configured(None, "hunter2") is False
    assert icloud_photos.is_configured("user@example.com", None) is False
    assert icloud_photos.is_configured("", "") is False


async def test_start_auth_connects_immediately_when_no_2fa_needed(monkeypatch):
    service = FakeService(requires_2fa=False)
    monkeypatch.setattr(icloud_photos, "_build_service", lambda u, p: service)

    result = await icloud_photos.start_auth("user@example.com", "hunter2")

    assert result == {"connected": True, "requires_2fa": False}
    assert cache.get(icloud_photos._SERVICE_CACHE_KEY) is service


async def test_start_auth_reports_2fa_required(monkeypatch):
    service = FakeService(requires_2fa=True)
    monkeypatch.setattr(icloud_photos, "_build_service", lambda u, p: service)

    result = await icloud_photos.start_auth("user@example.com", "hunter2")

    assert result == {"connected": False, "requires_2fa": True}
    assert cache.get(icloud_photos._SERVICE_CACHE_KEY) is None
    assert cache.get(icloud_photos._PENDING_SERVICE_CACHE_KEY) is service


async def test_start_auth_handles_failed_login(monkeypatch):
    def _fail(u, p):
        raise ICloudPyFailedLoginException("bad credentials")

    monkeypatch.setattr(icloud_photos, "_build_service", _fail)

    result = await icloud_photos.start_auth("user@example.com", "wrong")

    assert result == {"connected": False, "requires_2fa": False}


async def test_verify_2fa_with_no_pending_service_fails():
    assert await icloud_photos.verify_2fa("123456") is False


async def test_verify_2fa_rejects_wrong_code(monkeypatch):
    service = FakeService(requires_2fa=True)
    monkeypatch.setattr(icloud_photos, "_build_service", lambda u, p: service)
    await icloud_photos.start_auth("user@example.com", "hunter2")

    assert await icloud_photos.verify_2fa("000000") is False
    assert cache.get(icloud_photos._SERVICE_CACHE_KEY) is None


async def test_verify_2fa_trusts_session_and_caches_service(monkeypatch):
    service = FakeService(requires_2fa=True)
    monkeypatch.setattr(icloud_photos, "_build_service", lambda u, p: service)
    await icloud_photos.start_auth("user@example.com", "hunter2")

    assert await icloud_photos.verify_2fa("123456") is True
    assert service.trust_session_called is True
    assert cache.get(icloud_photos._PENDING_SERVICE_CACHE_KEY) is None
    assert cache.get(icloud_photos._SERVICE_CACHE_KEY) is service


def test_is_connected_cached():
    assert icloud_photos.is_connected_cached() is False
    cache.set(icloud_photos._SERVICE_CACHE_KEY, object(), 60)
    assert icloud_photos.is_connected_cached() is True


async def test_list_photos_returns_assets_from_named_album(monkeypatch):
    asset = FakeAsset("id-1", "photo.jpg")
    service = FakeService(albums={"All Photos": FakeAlbum([asset])})
    monkeypatch.setattr(icloud_photos, "_build_service", lambda u, p: service)

    photos = await icloud_photos.list_photos("user@example.com", "hunter2")

    assert photos == [{"id": "id-1", "filename": "photo.jpg"}]


async def test_list_photos_returns_empty_for_missing_album(monkeypatch):
    service = FakeService(albums={})
    monkeypatch.setattr(icloud_photos, "_build_service", lambda u, p: service)

    photos = await icloud_photos.list_photos("user@example.com", "hunter2")

    assert photos == []


async def test_list_photos_is_cached_across_calls(monkeypatch):
    asset = FakeAsset("id-1", "photo.jpg")
    service = FakeService(albums={"All Photos": FakeAlbum([asset])})
    calls = 0

    def _build(u, p):
        nonlocal calls
        calls += 1
        return service

    monkeypatch.setattr(icloud_photos, "_build_service", _build)

    await icloud_photos.list_photos("user@example.com", "hunter2")
    await icloud_photos.list_photos("user@example.com", "hunter2")

    assert calls == 1


async def test_fetch_photo_bytes_returns_content_and_type(monkeypatch):
    asset = FakeAsset("id-1", "photo.jpg", content=b"jpeg-bytes")
    service = FakeService(albums={"All Photos": FakeAlbum([asset])})
    monkeypatch.setattr(icloud_photos, "_build_service", lambda u, p: service)

    result = await icloud_photos.fetch_photo_bytes("user@example.com", "hunter2", "id-1")

    assert result == (b"jpeg-bytes", "image/jpeg")


async def test_fetch_photo_bytes_returns_none_for_unknown_id(monkeypatch):
    service = FakeService(albums={"All Photos": FakeAlbum([])})
    monkeypatch.setattr(icloud_photos, "_build_service", lambda u, p: service)

    result = await icloud_photos.fetch_photo_bytes("user@example.com", "hunter2", "missing")

    assert result is None


async def test_iter_photo_chunks_yields_batches_from_the_named_album(monkeypatch):
    chunks = [
        [FakeAsset("id-1", "a.jpg"), FakeAsset("id-2", "b.jpg")],
        [FakeAsset("id-3", "c.jpg")],
    ]
    service = FakeService(albums={"All Photos": FakeAlbum([], chunks=chunks)})
    monkeypatch.setattr(icloud_photos, "_build_service", lambda u, p: service)

    seen = [chunk async for chunk in icloud_photos.iter_photo_chunks("user@example.com", "hunter2")]

    assert seen == [
        [{"id": "id-1", "filename": "a.jpg"}, {"id": "id-2", "filename": "b.jpg"}],
        [{"id": "id-3", "filename": "c.jpg"}],
    ]


async def test_iter_photo_chunks_yields_nothing_when_2fa_required(monkeypatch):
    service = FakeService(requires_2fa=True, albums={"All Photos": FakeAlbum([FakeAsset("id-1", "a.jpg")])})
    monkeypatch.setattr(icloud_photos, "_build_service", lambda u, p: service)

    seen = [chunk async for chunk in icloud_photos.iter_photo_chunks("user@example.com", "hunter2")]

    assert seen == []


async def test_iter_photo_chunks_yields_nothing_for_missing_album(monkeypatch):
    service = FakeService(albums={})
    monkeypatch.setattr(icloud_photos, "_build_service", lambda u, p: service)

    seen = [chunk async for chunk in icloud_photos.iter_photo_chunks("user@example.com", "hunter2")]

    assert seen == []
