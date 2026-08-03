from __future__ import annotations

import httpx
import pytest
import respx

from app.integrations import container_client

TCP_SETTINGS = {"connection": "tcp", "host": "docker.local", "port": 2375}
SOCKET_SETTINGS = {"connection": "socket", "socket_path": "/var/run/docker.sock"}

CONTAINERS_RESPONSE = [
    {
        "Id": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef012345678",
        "Names": ["/web"],
        "Image": "nginx:latest",
        "State": "running",
        "Status": "Up 2 hours",
    },
    {
        "Id": "111111111111222222222222333333333333444444444444555555555555ff",
        "Names": ["/worker"],
        "Image": "myapp:latest",
        "State": "exited",
        "Status": "Exited (0) 3 days ago",
    },
]


def test_is_configured_tcp_requires_host():
    assert container_client.is_configured(TCP_SETTINGS)
    assert not container_client.is_configured({"connection": "tcp", "host": ""})


def test_is_configured_socket_defaults_to_true():
    assert container_client.is_configured(SOCKET_SETTINGS)
    assert container_client.is_configured({})


@respx.mock
async def test_fetch_containers_over_tcp_maps_fields():
    route = respx.get("http://docker.local:2375/containers/json", params={"all": "true"}).mock(
        return_value=httpx.Response(200, json=CONTAINERS_RESPONSE)
    )

    containers = await container_client.fetch_containers(TCP_SETTINGS)

    assert route.called
    assert containers[0]["name"] == "web"
    assert containers[0]["state"] == "running"
    assert containers[0]["status"] == "Up 2 hours"
    assert containers[0]["image"] == "nginx:latest"
    assert containers[0]["id"] == "abcdef012345"
    assert containers[1]["name"] == "worker"
    assert containers[1]["state"] == "exited"


@respx.mock
async def test_fetch_containers_over_socket_maps_fields():
    respx.get("http://container/containers/json", params={"all": "true"}).mock(
        return_value=httpx.Response(200, json=CONTAINERS_RESPONSE)
    )

    containers = await container_client.fetch_containers(SOCKET_SETTINGS)

    assert len(containers) == 2
    assert containers[0]["name"] == "web"


def test_container_dict_falls_back_to_id_without_names():
    entry = {"Id": "abcdef0123456789", "Image": "x", "State": "running", "Status": "Up"}

    result = container_client._container_dict(entry)

    assert result["name"] == "abcdef012345"


@respx.mock
async def test_fetch_containers_raises_on_connect_error():
    respx.get("http://docker.local:2375/containers/json").mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(container_client.ContainerError):
        await container_client.fetch_containers(TCP_SETTINGS)


@respx.mock
async def test_fetch_containers_raises_on_server_error():
    respx.get("http://docker.local:2375/containers/json").mock(return_value=httpx.Response(500))

    with pytest.raises(container_client.ContainerError):
        await container_client.fetch_containers(TCP_SETTINGS)


@respx.mock
async def test_fetch_containers_raises_on_non_json_response():
    respx.get("http://docker.local:2375/containers/json").mock(
        return_value=httpx.Response(200, content=b"not json", headers={"content-type": "text/plain"})
    )

    with pytest.raises(container_client.ContainerError):
        await container_client.fetch_containers(TCP_SETTINGS)


@respx.mock
async def test_fetch_containers_raises_on_unexpected_shape():
    respx.get("http://docker.local:2375/containers/json").mock(return_value=httpx.Response(200, json={"oops": True}))

    with pytest.raises(container_client.ContainerError):
        await container_client.fetch_containers(TCP_SETTINGS)
