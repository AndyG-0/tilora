from __future__ import annotations

import httpx
import pytest
import respx

from app import update_check
from app.config import settings
from app.update_check import check_for_update, get_update_status

RELEASE_URL = f"https://api.github.com/repos/{settings.github_repo}/releases/latest"


@pytest.fixture(autouse=True)
def _reset_latest():
    update_check._latest["latest_version"] = None
    update_check._latest["release_url"] = None
    yield
    update_check._latest["latest_version"] = None
    update_check._latest["release_url"] = None


def test_no_check_yet_reports_no_update(monkeypatch):
    monkeypatch.setattr(update_check, "CURRENT_VERSION", "1.0.0")

    status = get_update_status()

    assert status == {
        "current_version": "1.0.0",
        "latest_version": None,
        "update_available": False,
        "release_url": None,
    }


@respx.mock
async def test_newer_release_marks_update_available(monkeypatch):
    monkeypatch.setattr(update_check, "CURRENT_VERSION", "1.0.0")
    respx.get(RELEASE_URL).mock(
        return_value=httpx.Response(
            200, json={"tag_name": "v1.1.0", "html_url": "https://github.com/x/releases/tag/v1.1.0"}
        )
    )

    await check_for_update()
    status = get_update_status()

    assert status["latest_version"] == "1.1.0"
    assert status["update_available"] is True
    assert status["release_url"] == "https://github.com/x/releases/tag/v1.1.0"


@respx.mock
async def test_same_or_older_release_does_not_mark_update_available(monkeypatch):
    monkeypatch.setattr(update_check, "CURRENT_VERSION", "1.0.0")
    respx.get(RELEASE_URL).mock(return_value=httpx.Response(200, json={"tag_name": "v1.0.0", "html_url": "https://x"}))

    await check_for_update()

    assert get_update_status()["update_available"] is False


@respx.mock
async def test_multi_digit_segments_compare_numerically(monkeypatch):
    monkeypatch.setattr(update_check, "CURRENT_VERSION", "0.9.0")
    respx.get(RELEASE_URL).mock(return_value=httpx.Response(200, json={"tag_name": "v0.10.0", "html_url": "https://x"}))

    await check_for_update()

    assert get_update_status()["update_available"] is True


@respx.mock
async def test_failed_check_keeps_previous_result(monkeypatch):
    monkeypatch.setattr(update_check, "CURRENT_VERSION", "1.0.0")
    update_check._latest["latest_version"] = "1.1.0"
    update_check._latest["release_url"] = "https://x"
    respx.get(RELEASE_URL).mock(return_value=httpx.Response(404))

    await check_for_update()

    status = get_update_status()
    assert status["latest_version"] == "1.1.0"
    assert status["release_url"] == "https://x"


@respx.mock
async def test_polls_the_configured_github_repo(monkeypatch):
    monkeypatch.setattr(settings, "github_repo", "someone-else/their-fork")
    route = respx.get("https://api.github.com/repos/someone-else/their-fork/releases/latest").mock(
        return_value=httpx.Response(200, json={"tag_name": "v2.0.0", "html_url": "https://x"})
    )

    await check_for_update()

    assert route.called
