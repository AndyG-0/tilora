from __future__ import annotations

import pytest

from app.integrations import speedtest_runner


class _FakeResults:
    def __init__(self, data: dict) -> None:
        self._data = data

    def dict(self) -> dict:
        return self._data


class _FakeSpeedtest:
    def __init__(self, results: dict) -> None:
        self.results = _FakeResults(results)

    def get_best_server(self) -> None: ...
    def download(self) -> None: ...
    def upload(self) -> None: ...


def test_run_speedtest_returns_mbps_and_server_name(monkeypatch):
    results = {
        "download": 300_000_000.0,
        "upload": 30_000_000.0,
        "ping": 12.5,
        "server": {"sponsor": "Acme ISP", "name": "Springfield"},
    }
    monkeypatch.setattr(speedtest_runner.speedtest, "Speedtest", lambda: _FakeSpeedtest(results))

    result = speedtest_runner.run_speedtest()

    assert result == {
        "download_mbps": 300.0,
        "upload_mbps": 30.0,
        "ping_ms": 12.5,
        "server_name": "Acme ISP",
    }


def test_run_speedtest_falls_back_to_server_name_when_no_sponsor(monkeypatch):
    results = {
        "download": 100_000_000.0,
        "upload": 10_000_000.0,
        "ping": 20.0,
        "server": {"name": "Springfield"},
    }
    monkeypatch.setattr(speedtest_runner.speedtest, "Speedtest", lambda: _FakeSpeedtest(results))

    result = speedtest_runner.run_speedtest()

    assert result["server_name"] == "Springfield"


def test_run_speedtest_raises_speedtest_error_when_client_fails(monkeypatch):
    def raise_error():
        raise RuntimeError("no servers available")

    monkeypatch.setattr(speedtest_runner.speedtest, "Speedtest", raise_error)

    with pytest.raises(speedtest_runner.SpeedtestError):
        speedtest_runner.run_speedtest()


def test_run_speedtest_raises_speedtest_error_on_unexpected_result_shape(monkeypatch):
    monkeypatch.setattr(speedtest_runner.speedtest, "Speedtest", lambda: _FakeSpeedtest({"server": {}}))

    with pytest.raises(speedtest_runner.SpeedtestError):
        speedtest_runner.run_speedtest()
