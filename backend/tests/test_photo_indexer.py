from __future__ import annotations

from app.config import settings
from app.integrations import icloud_photos
from app.plugins.photos.indexer import index_photos
from app.plugins.photos.plugin import PhotosPlugin
from app.storage import db


def make_plugin(tmp_path, **settings) -> PhotosPlugin:
    return PhotosPlugin({"id": "photos", "settings": {"directory": str(tmp_path), **settings}})


def make_private_plugin(**settings) -> PhotosPlugin:
    return PhotosPlugin({"id": "photos", "settings": {"provider": "icloud_private", **settings}})


async def test_index_photos_populates_from_local_directory(tmp_db, tmp_path):
    (tmp_path / "b.jpg").write_bytes(b"fake")
    (tmp_path / "a.jpg").write_bytes(b"fake")
    plugin = make_plugin(tmp_path)

    await index_photos(plugin)

    assert db.photo_index_photo_ids(plugin.id) == ["a.jpg", "b.jpg"]
    status = db.photo_index_status(plugin.id)
    assert status["status"] == "ok"
    assert status["last_error"] is None


async def test_index_photos_removes_stale_entries_on_rescan(tmp_db, tmp_path):
    a = tmp_path / "a.jpg"
    b = tmp_path / "b.jpg"
    a.write_bytes(b"fake")
    b.write_bytes(b"fake")
    plugin = make_plugin(tmp_path)

    await index_photos(plugin)
    assert db.photo_index_photo_ids(plugin.id) == ["a.jpg", "b.jpg"]

    b.unlink()
    (tmp_path / "c.jpg").write_bytes(b"fake")
    await index_photos(plugin)

    assert db.photo_index_photo_ids(plugin.id) == ["a.jpg", "c.jpg"]


async def test_failed_scan_preserves_previous_index_and_marks_status_error(tmp_db, tmp_path, monkeypatch):
    (tmp_path / "a.jpg").write_bytes(b"fake")
    plugin = make_plugin(tmp_path)
    await index_photos(plugin)
    assert db.photo_index_photo_ids(plugin.id) == ["a.jpg"]

    async def boom():
        raise RuntimeError("source unreachable")
        yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(plugin, "_enumerate_photo_ids_chunks", boom)
    await index_photos(plugin)

    assert db.photo_index_photo_ids(plugin.id) == ["a.jpg"]
    status = db.photo_index_status(plugin.id)
    assert status["status"] == "error"
    assert "source unreachable" in status["last_error"]


async def test_chunked_indexing_accumulates_positions_across_many_chunks(monkeypatch, tmp_db):
    monkeypatch.setattr(settings, "icloud_username", "user@example.com")
    monkeypatch.setattr(settings, "icloud_password", "hunter2")

    chunk_count = 25
    chunk_size = 4

    async def fake_iter_photo_chunks(username, password, album_name):
        for chunk_index in range(chunk_count):
            yield [{"id": f"id-{chunk_index}-{i}", "filename": f"{chunk_index}-{i}.jpg"} for i in range(chunk_size)]

    monkeypatch.setattr(icloud_photos, "iter_photo_chunks", fake_iter_photo_chunks)
    plugin = make_private_plugin()

    await index_photos(plugin)

    photo_ids = db.photo_index_photo_ids(plugin.id)
    assert len(photo_ids) == chunk_count * chunk_size
    expected = [f"id-{chunk_index}-{i}" for chunk_index in range(chunk_count) for i in range(chunk_size)]
    assert photo_ids == expected
