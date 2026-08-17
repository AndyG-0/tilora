from icloudpy.exceptions import ICloudPyAPIResponseException, ICloudPyFailedLoginException

from app.integrations import icloud_photos
from app.storage.cache import cache

USER_ID = "alice"
OTHER_USER_ID = "bob"


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
    def __init__(
        self,
        requires_2fa: bool = False,
        albums: dict[str, FakeAlbum] | None = None,
        push_notification_succeeds: bool = True,
    ):
        self.requires_2fa = requires_2fa
        self.is_trusted_session = False
        self.photos = FakePhotosService(albums or {})
        self._2fa_valid_code = "123456"
        self.trust_session_called = False
        self._push_notification_succeeds = push_notification_succeeds
        self.trigger_2fa_push_notification_called = False

    def validate_2fa_code(self, code: str) -> bool:
        return code == self._2fa_valid_code

    def trust_session(self) -> None:
        self.trust_session_called = True
        self.is_trusted_session = True

    def trigger_2fa_push_notification(self) -> bool:
        self.trigger_2fa_push_notification_called = True
        return self._push_notification_succeeds


def test_is_configured():
    assert icloud_photos.is_configured("user@example.com", "hunter2") is True
    assert icloud_photos.is_configured(None, "hunter2") is False
    assert icloud_photos.is_configured("user@example.com", None) is False
    assert icloud_photos.is_configured("", "") is False


async def test_start_auth_connects_immediately_when_no_2fa_needed(monkeypatch):
    service = FakeService(requires_2fa=False)
    monkeypatch.setattr(icloud_photos, "_build_service", lambda user_id, u, p: service)

    result = await icloud_photos.start_auth(USER_ID, "user@example.com", "hunter2")

    assert result == {"connected": True, "requires_2fa": False}
    assert cache.get(icloud_photos._service_cache_key(USER_ID)) is service


async def test_start_auth_reports_2fa_required(monkeypatch):
    service = FakeService(requires_2fa=True)
    monkeypatch.setattr(icloud_photos, "_build_service", lambda user_id, u, p: service)

    result = await icloud_photos.start_auth(USER_ID, "user@example.com", "hunter2")

    assert result == {"connected": False, "requires_2fa": True}
    assert cache.get(icloud_photos._service_cache_key(USER_ID)) is None
    assert cache.get(icloud_photos._pending_service_cache_key(USER_ID)) is service
    assert service.trigger_2fa_push_notification_called is True


async def test_start_auth_still_reports_2fa_required_when_push_trigger_fails(monkeypatch):
    service = FakeService(requires_2fa=True, push_notification_succeeds=False)
    monkeypatch.setattr(icloud_photos, "_build_service", lambda user_id, u, p: service)

    result = await icloud_photos.start_auth(USER_ID, "user@example.com", "hunter2")

    assert result == {"connected": False, "requires_2fa": True}
    assert service.trigger_2fa_push_notification_called is True
    assert cache.get(icloud_photos._pending_service_cache_key(USER_ID)) is service


async def test_start_auth_handles_failed_login(monkeypatch):
    def _fail(user_id, u, p):
        raise ICloudPyFailedLoginException("bad credentials")

    monkeypatch.setattr(icloud_photos, "_build_service", _fail)

    result = await icloud_photos.start_auth(USER_ID, "user@example.com", "wrong")

    assert result["connected"] is False
    assert result["requires_2fa"] is False
    assert "error" in result


async def test_start_auth_handles_503_throttling(monkeypatch):
    def _fail(user_id, u, p):
        raise ICloudPyFailedLoginException(
            "Failed to initiate srp", ICloudPyAPIResponseException("Service Unavailable", 503)
        )

    monkeypatch.setattr(icloud_photos, "_build_service", _fail)

    result = await icloud_photos.start_auth(USER_ID, "user@example.com", "hunter2")

    assert result["connected"] is False
    assert result["requires_2fa"] is False
    assert "503" in result["error"]


async def test_verify_2fa_with_no_pending_service_fails():
    assert await icloud_photos.verify_2fa(USER_ID, "123456") is False


async def test_verify_2fa_rejects_wrong_code(monkeypatch):
    service = FakeService(requires_2fa=True)
    monkeypatch.setattr(icloud_photos, "_build_service", lambda user_id, u, p: service)
    await icloud_photos.start_auth(USER_ID, "user@example.com", "hunter2")

    assert await icloud_photos.verify_2fa(USER_ID, "000000") is False
    assert cache.get(icloud_photos._service_cache_key(USER_ID)) is None


async def test_verify_2fa_trusts_session_and_caches_service(monkeypatch):
    service = FakeService(requires_2fa=True)
    monkeypatch.setattr(icloud_photos, "_build_service", lambda user_id, u, p: service)
    await icloud_photos.start_auth(USER_ID, "user@example.com", "hunter2")

    assert await icloud_photos.verify_2fa(USER_ID, "123456") is True
    assert service.trust_session_called is True
    assert cache.get(icloud_photos._pending_service_cache_key(USER_ID)) is None
    assert cache.get(icloud_photos._service_cache_key(USER_ID)) is service


def test_is_connected_cached():
    assert icloud_photos.is_connected_cached(USER_ID) is False
    cache.set(icloud_photos._service_cache_key(USER_ID), object(), 60)
    assert icloud_photos.is_connected_cached(USER_ID) is True


def test_is_connected_cached_is_independent_per_user():
    cache.set(icloud_photos._service_cache_key(USER_ID), object(), 60)

    assert icloud_photos.is_connected_cached(OTHER_USER_ID) is False


def test_invalidate_service_cache_drops_service_pending_and_photo_list():
    cache.set(icloud_photos._service_cache_key(USER_ID), object(), 60)
    cache.set(icloud_photos._pending_service_cache_key(USER_ID), object(), 60)
    cache.set(icloud_photos._photo_list_cache_key(USER_ID), [object()], 60)

    icloud_photos.invalidate_service_cache(USER_ID)

    assert cache.get(icloud_photos._service_cache_key(USER_ID)) is None
    assert cache.get(icloud_photos._pending_service_cache_key(USER_ID)) is None
    assert cache.get(icloud_photos._photo_list_cache_key(USER_ID)) is None


def test_invalidate_service_cache_leaves_other_users_cache_intact():
    cache.set(icloud_photos._service_cache_key(OTHER_USER_ID), object(), 60)

    icloud_photos.invalidate_service_cache(USER_ID)

    assert cache.get(icloud_photos._service_cache_key(OTHER_USER_ID)) is not None


async def test_list_photos_returns_assets_from_named_album(monkeypatch):
    asset = FakeAsset("id-1", "photo.jpg")
    service = FakeService(albums={"All Photos": FakeAlbum([asset])})
    monkeypatch.setattr(icloud_photos, "_build_service", lambda user_id, u, p: service)

    photos = await icloud_photos.list_photos(USER_ID, "user@example.com", "hunter2")

    assert photos == [{"id": "id-1", "filename": "photo.jpg"}]


async def test_list_photos_returns_empty_for_missing_album(monkeypatch):
    service = FakeService(albums={})
    monkeypatch.setattr(icloud_photos, "_build_service", lambda user_id, u, p: service)

    photos = await icloud_photos.list_photos(USER_ID, "user@example.com", "hunter2")

    assert photos == []


async def test_list_photos_is_cached_across_calls(monkeypatch):
    asset = FakeAsset("id-1", "photo.jpg")
    service = FakeService(albums={"All Photos": FakeAlbum([asset])})
    calls = 0

    def _build(user_id, u, p):
        nonlocal calls
        calls += 1
        return service

    monkeypatch.setattr(icloud_photos, "_build_service", _build)

    await icloud_photos.list_photos(USER_ID, "user@example.com", "hunter2")
    await icloud_photos.list_photos(USER_ID, "user@example.com", "hunter2")

    assert calls == 1


async def test_list_photos_cache_is_independent_per_user(monkeypatch):
    asset = FakeAsset("id-1", "photo.jpg")
    service = FakeService(albums={"All Photos": FakeAlbum([asset])})
    calls = 0

    def _build(user_id, u, p):
        nonlocal calls
        calls += 1
        return service

    monkeypatch.setattr(icloud_photos, "_build_service", _build)

    await icloud_photos.list_photos(USER_ID, "user@example.com", "hunter2")
    await icloud_photos.list_photos(OTHER_USER_ID, "other@example.com", "hunter3")

    assert calls == 2


async def test_fetch_photo_bytes_returns_content_and_type(monkeypatch):
    asset = FakeAsset("id-1", "photo.jpg", content=b"jpeg-bytes")
    service = FakeService(albums={"All Photos": FakeAlbum([asset])})
    monkeypatch.setattr(icloud_photos, "_build_service", lambda user_id, u, p: service)

    result = await icloud_photos.fetch_photo_bytes(USER_ID, "user@example.com", "hunter2", "id-1")

    assert result == (b"jpeg-bytes", "image/jpeg")


async def test_fetch_photo_bytes_returns_none_for_unknown_id(monkeypatch):
    service = FakeService(albums={"All Photos": FakeAlbum([])})
    monkeypatch.setattr(icloud_photos, "_build_service", lambda user_id, u, p: service)

    result = await icloud_photos.fetch_photo_bytes(USER_ID, "user@example.com", "hunter2", "missing")

    assert result is None


async def test_iter_photo_chunks_yields_batches_from_the_named_album(monkeypatch):
    chunks = [
        [FakeAsset("id-1", "a.jpg"), FakeAsset("id-2", "b.jpg")],
        [FakeAsset("id-3", "c.jpg")],
    ]
    service = FakeService(albums={"All Photos": FakeAlbum([], chunks=chunks)})
    monkeypatch.setattr(icloud_photos, "_build_service", lambda user_id, u, p: service)

    seen = [chunk async for chunk in icloud_photos.iter_photo_chunks(USER_ID, "user@example.com", "hunter2")]

    assert seen == [
        [{"id": "id-1", "filename": "a.jpg"}, {"id": "id-2", "filename": "b.jpg"}],
        [{"id": "id-3", "filename": "c.jpg"}],
    ]


async def test_iter_photo_chunks_yields_nothing_when_2fa_required(monkeypatch):
    service = FakeService(requires_2fa=True, albums={"All Photos": FakeAlbum([FakeAsset("id-1", "a.jpg")])})
    monkeypatch.setattr(icloud_photos, "_build_service", lambda user_id, u, p: service)

    seen = [chunk async for chunk in icloud_photos.iter_photo_chunks(USER_ID, "user@example.com", "hunter2")]

    assert seen == []


async def test_iter_photo_chunks_yields_nothing_for_missing_album(monkeypatch):
    service = FakeService(albums={})
    monkeypatch.setattr(icloud_photos, "_build_service", lambda user_id, u, p: service)

    seen = [chunk async for chunk in icloud_photos.iter_photo_chunks(USER_ID, "user@example.com", "hunter2")]

    assert seen == []


async def test_start_auth_handles_api_response_exception(monkeypatch):
    def _fail(user_id, u, p):
        raise ICloudPyAPIResponseException("Authentication required for Account.", 421)

    monkeypatch.setattr(icloud_photos, "_build_service", _fail)

    result = await icloud_photos.start_auth(USER_ID, "user@example.com", "hunter2")

    assert result["connected"] is False
    assert result["requires_2fa"] is False
    assert "error" in result


async def test_verify_2fa_handles_api_exception(monkeypatch):
    service = FakeService(requires_2fa=True)
    monkeypatch.setattr(icloud_photos, "_build_service", lambda user_id, u, p: service)
    await icloud_photos.start_auth(USER_ID, "user@example.com", "hunter2")

    def _boom(code):
        raise ICloudPyAPIResponseException("Server Error", 500)

    monkeypatch.setattr(service, "validate_2fa_code", _boom)

    assert await icloud_photos.verify_2fa(USER_ID, "123456") is False


async def test_list_photos_handles_421_auth_error_and_invalidates_cache(monkeypatch):
    class ExplodingAlbum:
        @property
        def photos(self):
            raise ICloudPyAPIResponseException("Authentication required for Account.", 421)

    service = FakeService(albums={"All Photos": ExplodingAlbum()})
    monkeypatch.setattr(icloud_photos, "_build_service", lambda user_id, u, p: service)
    cache.set(icloud_photos._service_cache_key(USER_ID), service, 60)

    photos = await icloud_photos.list_photos(USER_ID, "user@example.com", "hunter2")

    assert photos == []
    # Cache should be invalidated because 421 is an auth error
    assert cache.get(icloud_photos._service_cache_key(USER_ID)) is None


async def test_list_photos_handles_general_exception(monkeypatch):
    class ExplodingAlbum:
        @property
        def photos(self):
            raise RuntimeError("unexpected network failure")

    service = FakeService(albums={"All Photos": ExplodingAlbum()})
    monkeypatch.setattr(icloud_photos, "_build_service", lambda user_id, u, p: service)

    photos = await icloud_photos.list_photos(USER_ID, "user@example.com", "hunter2")

    assert photos == []


async def test_fetch_photo_bytes_handles_421_on_download_and_invalidates_cache(monkeypatch):
    class ExplodingAsset(FakeAsset):
        def download(self, version: str = "original"):
            raise ICloudPyAPIResponseException("Authentication required for Account.", 421)

    asset = ExplodingAsset("id-1", "photo.jpg")
    service = FakeService(albums={"All Photos": FakeAlbum([asset])})
    monkeypatch.setattr(icloud_photos, "_build_service", lambda user_id, u, p: service)
    cache.set(icloud_photos._service_cache_key(USER_ID), service, 60)

    result = await icloud_photos.fetch_photo_bytes(USER_ID, "user@example.com", "hunter2", "id-1")

    assert result is None
    assert cache.get(icloud_photos._service_cache_key(USER_ID)) is None


async def test_fetch_photo_bytes_handles_general_download_exception(monkeypatch):
    class ExplodingAsset(FakeAsset):
        def download(self, version: str = "original"):
            raise RuntimeError("connection reset")

    asset = ExplodingAsset("id-1", "photo.jpg")
    service = FakeService(albums={"All Photos": FakeAlbum([asset])})
    monkeypatch.setattr(icloud_photos, "_build_service", lambda user_id, u, p: service)

    result = await icloud_photos.fetch_photo_bytes(USER_ID, "user@example.com", "hunter2", "id-1")

    assert result is None


async def test_iter_photo_chunks_handles_421_and_invalidates_cache(monkeypatch):
    class ExplodingAlbum:
        def iter_chunks(self, chunk_size: int):
            raise ICloudPyAPIResponseException("Authentication required for Account.", 421)
            yield []  # pragma: no cover

    service = FakeService(albums={"All Photos": ExplodingAlbum()})
    monkeypatch.setattr(icloud_photos, "_build_service", lambda user_id, u, p: service)
    cache.set(icloud_photos._service_cache_key(USER_ID), service, 60)

    seen = [chunk async for chunk in icloud_photos.iter_photo_chunks(USER_ID, "user@example.com", "hunter2")]

    assert seen == []
    assert cache.get(icloud_photos._service_cache_key(USER_ID)) is None


async def test_get_or_build_service_handles_api_response_exception(monkeypatch):
    def _fail(user_id, u, p):
        raise ICloudPyAPIResponseException("Unauthorized", 401)

    monkeypatch.setattr(icloud_photos, "_build_service", _fail)

    service, err = await icloud_photos._get_or_build_service(USER_ID, "user@example.com", "hunter2")

    assert service is None
    assert err is not None
    assert cache.get(icloud_photos._service_cache_key(USER_ID)) is None
