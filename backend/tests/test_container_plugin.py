from __future__ import annotations

import httpx
import pytest
import respx

from app.plugins.container.plugin import ContainerPlugin

CONTAINERS_RESPONSE = [
    {"Id": "aaaaaaaaaaaa1111", "Names": ["/web"], "Image": "nginx:latest", "State": "running", "Status": "Up 2 hours"},
    {
        "Id": "bbbbbbbbbbbb2222",
        "Names": ["/worker"],
        "Image": "myapp:latest",
        "State": "exited",
        "Status": "Exited (1) 3 days ago",
    },
]

ENGINE_TCP_SETTINGS = {
    "docker": {"engine": "docker", "connection": "tcp", "host": "docker.local", "port": 2375},
    "podman": {"engine": "podman", "connection": "tcp", "host": "podman.local", "port": 8080},
}
ENGINE_SOCKET_PATHS = {"docker": "/var/run/docker.sock", "podman": "/run/podman/podman.sock"}


def make_plugin(**settings) -> ContainerPlugin:
    return ContainerPlugin({"id": "container", "settings": {**ContainerPlugin.default_settings, **settings}})


@pytest.mark.parametrize("engine", ["docker", "podman"])
async def test_get_summary_when_not_configured(engine):
    plugin = make_plugin(engine=engine, connection="tcp", host="")

    summary = await plugin.get_summary()

    assert summary["connected"] is False
    assert summary["containers"] == []
    assert summary["total_count"] == 0


@pytest.mark.parametrize("engine", ["docker", "podman"])
async def test_get_summary_defaults_to_socket_connection_for_engine(engine):
    # No `socket_path` key at all (unlike make_plugin, which always merges
    # in default_settings' docker-flavored one) — isolates _settings_view's
    # own per-engine fallback from the class-level default_settings.
    plugin = ContainerPlugin({"id": "container", "settings": {"engine": engine}})

    summary = await plugin.get_summary()

    assert summary["engine"] == engine
    assert summary["connection"] == "socket"
    assert summary["socket_path"] == ENGINE_SOCKET_PATHS[engine]


@pytest.mark.parametrize("engine", ["docker", "podman"])
@respx.mock
async def test_get_summary_when_connected_reports_counts(engine):
    tcp_settings = ENGINE_TCP_SETTINGS[engine]
    respx.get(f"http://{tcp_settings['host']}:{tcp_settings['port']}/containers/json", params={"all": "true"}).mock(
        return_value=httpx.Response(200, json=CONTAINERS_RESPONSE)
    )
    plugin = make_plugin(**tcp_settings)

    summary = await plugin.get_summary()

    assert summary["connected"] is True
    assert summary["running_count"] == 1
    assert summary["stopped_count"] == 1
    assert summary["total_count"] == 2
    assert summary["containers"] == [
        {"name": "web", "state": "running", "status": "Up 2 hours"},
        {"name": "worker", "state": "exited", "status": "Exited (1) 3 days ago"},
    ]


@respx.mock
async def test_get_summary_surfaces_error_without_raising():
    respx.get("http://docker.local:2375/containers/json").mock(side_effect=httpx.ConnectError("refused"))
    plugin = make_plugin(**ENGINE_TCP_SETTINGS["docker"])

    summary = await plugin.get_summary()

    assert summary["connected"] is True
    assert "error" in summary
    assert summary["containers"] == []
    assert summary["total_count"] == 0


@respx.mock
async def test_get_detail_includes_image_and_id():
    containers_route = respx.get("http://docker.local:2375/containers/json", params={"all": "true"}).mock(
        return_value=httpx.Response(200, json=CONTAINERS_RESPONSE)
    )
    plugin = make_plugin(**ENGINE_TCP_SETTINGS["docker"])

    detail = await plugin.get_detail()

    assert detail["containers"] == [
        {"id": "aaaaaaaaaaaa", "name": "web", "image": "nginx:latest", "state": "running", "status": "Up 2 hours"},
        {
            "id": "bbbbbbbbbbbb",
            "name": "worker",
            "image": "myapp:latest",
            "state": "exited",
            "status": "Exited (1) 3 days ago",
        },
    ]
    # Regression: get_detail() must share the one containers fetch with
    # get_summary() rather than redundantly re-fetching it.
    assert containers_route.call_count == 1


async def test_get_detail_when_not_configured():
    plugin = make_plugin(connection="tcp", host="")

    detail = await plugin.get_detail()

    assert detail["connected"] is False
    assert detail["containers"] == []


@respx.mock
async def test_get_detail_surfaces_error_without_raising():
    respx.get("http://docker.local:2375/containers/json").mock(return_value=httpx.Response(500))
    plugin = make_plugin(**ENGINE_TCP_SETTINGS["docker"])

    detail = await plugin.get_detail()

    assert detail["connected"] is True
    assert "error" in detail
    assert detail["containers"] == []


@pytest.mark.parametrize("engine", ["docker", "podman"])
async def test_get_ai_tools_returns_status_tool_named_for_engine(engine):
    plugin = make_plugin(engine=engine, connection="tcp", host="")

    tools = plugin.get_ai_tools()

    assert len(tools) == 1
    assert tools[0].name == f"get_{engine}_container_status"
    result = await tools[0].handler()
    assert result["connected"] is False
