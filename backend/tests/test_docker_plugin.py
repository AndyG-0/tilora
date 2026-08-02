from __future__ import annotations

import httpx
import respx

from app.plugins.docker.plugin import DockerPlugin

TCP_SETTINGS = {"connection": "tcp", "host": "docker.local", "port": 2375}

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


def make_plugin(**settings) -> DockerPlugin:
    return DockerPlugin({"id": "docker", "settings": {**DockerPlugin.default_settings, **settings}})


async def test_get_summary_when_not_configured():
    plugin = make_plugin(connection="tcp", host="")

    summary = await plugin.get_summary()

    assert summary["connected"] is False
    assert summary["containers"] == []
    assert summary["total_count"] == 0


async def test_get_summary_defaults_to_socket_connection():
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["connection"] == "socket"
    assert summary["socket_path"] == "/var/run/docker.sock"


@respx.mock
async def test_get_summary_when_connected_reports_counts():
    respx.get("http://docker.local:2375/containers/json", params={"all": "true"}).mock(
        return_value=httpx.Response(200, json=CONTAINERS_RESPONSE)
    )
    plugin = make_plugin(**TCP_SETTINGS)

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
    plugin = make_plugin(**TCP_SETTINGS)

    summary = await plugin.get_summary()

    assert summary["connected"] is True
    assert "error" in summary
    assert summary["containers"] == []
    assert summary["total_count"] == 0


@respx.mock
async def test_get_detail_includes_image_and_id():
    respx.get("http://docker.local:2375/containers/json", params={"all": "true"}).mock(
        return_value=httpx.Response(200, json=CONTAINERS_RESPONSE)
    )
    plugin = make_plugin(**TCP_SETTINGS)

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


async def test_get_detail_when_not_configured():
    plugin = make_plugin(connection="tcp", host="")

    detail = await plugin.get_detail()

    assert detail["connected"] is False
    assert detail["containers"] == []


@respx.mock
async def test_get_detail_surfaces_error_without_raising():
    respx.get("http://docker.local:2375/containers/json").mock(return_value=httpx.Response(500))
    plugin = make_plugin(**TCP_SETTINGS)

    detail = await plugin.get_detail()

    assert detail["connected"] is True
    assert "error" in detail
    assert detail["containers"] == []


async def test_get_ai_tools_returns_status_tool():
    plugin = make_plugin(connection="tcp", host="")

    tools = plugin.get_ai_tools()

    assert len(tools) == 1
    assert tools[0].name == "get_docker_container_status"
    result = await tools[0].handler()
    assert result["connected"] is False
