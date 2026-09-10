from __future__ import annotations

import subprocess
from unittest.mock import Mock

import httpx
import pytest
import respx

from app import update_check
from app.config import settings
from app.update_check import check_for_update, get_update_status, run_update

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
        "install_method": update_check.INSTALL_METHOD,
        "update_running": False,
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


@pytest.fixture(autouse=True)
def _reset_update_state():
    update_check._update_state["running"] = False
    update_check._update_state["error"] = None
    yield
    update_check._update_state["running"] = False
    update_check._update_state["error"] = None


async def test_run_update_passes_a_timeout_to_every_subprocess_call(monkeypatch):
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return Mock(returncode=0)

    monkeypatch.setattr(update_check.subprocess, "run", fake_run)

    await run_update()

    assert len(calls) == 6
    timeouts = [kwargs["timeout"] for _, kwargs in calls]
    assert timeouts == [
        update_check._GIT_TIMEOUT_SECONDS,
        update_check._GIT_MERGE_TIMEOUT_SECONDS,
        update_check._BUILD_STEP_TIMEOUT_SECONDS,
        update_check._BUILD_STEP_TIMEOUT_SECONDS,
        update_check._BUILD_STEP_TIMEOUT_SECONDS,
        update_check._RESTART_TIMEOUT_SECONDS,
    ]
    assert update_check._update_state["error"] is None
    assert update_check._update_state["running"] is False


async def test_run_update_handles_a_stalled_step_timing_out(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout", 0))

    monkeypatch.setattr(update_check.subprocess, "run", fake_run)

    await run_update()

    assert update_check._update_state["error"] == "Update failed — check the service logs for details."
    assert update_check._update_state["running"] is False


def test_get_update_status_includes_install_method(monkeypatch):
    monkeypatch.setattr(update_check, "CURRENT_VERSION", "1.0.0")
    monkeypatch.setattr(update_check, "INSTALL_METHOD", "native")

    status = get_update_status()

    assert status["install_method"] == "native"


def test_get_update_status_includes_update_running_flag():
    update_check._update_state["running"] = True
    try:
        status = get_update_status()
        assert status["update_running"] is True
    finally:
        update_check._update_state["running"] = False


def test_get_update_status_update_running_false_by_default():
    status = get_update_status()
    assert status["update_running"] is False
