from __future__ import annotations

from dataclasses import dataclass, field

import asyncssh
import pytest

from app.integrations import asus_router_client

SETTINGS = {"host": "router.local", "ssh_port": 22, "username": "admin", "password": "secret"}


@dataclass
class _FakeCompletedProcess:
    stdout: str


@dataclass
class _FakeConnection:
    stdout: str = ""
    run_error: Exception | None = None
    run_calls: int = field(default=0, init=False)
    closed: bool = field(default=False, init=False)

    async def run(self, command: str, check: bool = False):
        self.run_calls += 1
        if self.run_error is not None:
            raise self.run_error
        return _FakeCompletedProcess(stdout=self.stdout)

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        pass


def _fake_connect(*, stdout: str = "", connect_error: Exception | None = None, run_error: Exception | None = None):
    calls: list[dict] = []
    connection = _FakeConnection(stdout=stdout, run_error=run_error)

    async def fake_connect(host, *, port, username, password, known_hosts):
        calls.append({"host": host, "port": port, "username": username, "password": password})
        if connect_error is not None:
            raise connect_error
        return connection

    fake_connect.calls = calls
    fake_connect.connection = connection
    return fake_connect


def _build_output(
    *,
    wan_state: str = "2",
    wan_ip: str = "203.0.113.5",
    wan_ifname: str = "eth0",
    productid: str = "RT-AX88U",
    netdev_lines: list[str] | None = None,
    leases_lines: list[str] | None = None,
    arp_lines: list[str] | None = None,
) -> str:
    # /proc/net/dev: 8 receive fields (bytes first) then 8 transmit fields
    # (bytes first, at index 8) per "iface: ..." line.
    if netdev_lines is None:
        netdev_lines = [
            "  lo: 100 1 0 0 0 0 0 0 100 1 0 0 0 0 0 0",
            "eth0: 1024 10 0 0 0 0 0 0 512 5 0 0 0 0 0 0",
        ]
    if leases_lines is None:
        leases_lines = ["1700000000 aa:bb:cc:dd:ee:ff 192.168.1.10 Laptop 01:aa:bb:cc:dd:ee:ff"]
    if arp_lines is None:
        arp_lines = [
            "IP address       HW type     Flags       HW address            Mask     Device",
            "192.168.1.10     0x1         0x2         aa:bb:cc:dd:ee:ff     *        br0",
            "192.168.1.11     0x1         0x0         11:22:33:44:55:66     *        br0",
        ]
    sections = [
        ("WAN_STATE", [wan_state]),
        ("WAN_IP", [wan_ip]),
        ("WAN_IFNAME", [wan_ifname]),
        ("PRODUCTID", [productid]),
        ("NETDEV", netdev_lines),
        ("LEASES", leases_lines),
        ("ARP", arp_lines),
    ]
    lines: list[str] = []
    for name, section_lines in sections:
        lines.append(f"@@{name}@@")
        lines.extend(section_lines)
    return "\n".join(lines)


def test_is_configured_true_when_host_username_password_set():
    assert asus_router_client.is_configured(SETTINGS)


def test_is_configured_false_without_username():
    assert not asus_router_client.is_configured({"host": "router.local", "password": "secret"})


def test_is_configured_false_without_password():
    assert not asus_router_client.is_configured({"host": "router.local", "username": "admin"})


async def test_test_connection_returns_product_id(monkeypatch):
    fake = _fake_connect(stdout=_build_output(productid="RT-AX88U"))
    monkeypatch.setattr(asyncssh, "connect", fake)

    product_id = await asus_router_client.test_connection(SETTINGS, "test-widget")

    assert product_id == "RT-AX88U"
    assert fake.calls == [{"host": "router.local", "port": 22, "username": "admin", "password": "secret"}]


async def test_connect_coerces_string_ssh_port(monkeypatch):
    fake = _fake_connect(stdout=_build_output())
    monkeypatch.setattr(asyncssh, "connect", fake)

    await asus_router_client.test_connection({**SETTINGS, "ssh_port": "2222"}, "test-widget")

    assert fake.calls[0]["port"] == 2222


async def test_test_connection_bypasses_cache(monkeypatch):
    fake = _fake_connect(stdout=_build_output())
    monkeypatch.setattr(asyncssh, "connect", fake)

    await asus_router_client.get_wan_status(SETTINGS, "test-widget")
    await asus_router_client.test_connection(SETTINGS, "test-widget")

    # get_wan_status primes the cache; test_connection must still hit the
    # router directly since it's validating not-yet-saved candidate settings.
    assert fake.connection.run_calls == 2


async def test_poll_calls_share_one_ssh_round_trip_within_cache_ttl(monkeypatch):
    fake = _fake_connect(stdout=_build_output())
    monkeypatch.setattr(asyncssh, "connect", fake)

    await asus_router_client.get_wan_status(SETTINGS, "test-widget")
    await asus_router_client.get_clients(SETTINGS, "test-widget")
    await asus_router_client.get_traffic(SETTINGS, "test-widget")

    assert len(fake.calls) == 1
    assert fake.connection.run_calls == 1


async def test_get_wan_status_connected(monkeypatch):
    fake = _fake_connect(stdout=_build_output(wan_state="2", wan_ip="203.0.113.5"))
    monkeypatch.setattr(asyncssh, "connect", fake)

    status = await asus_router_client.get_wan_status(SETTINGS, "test-widget")

    assert status == {"connected": True, "ip": "203.0.113.5"}


async def test_get_wan_status_disconnected_for_non_connected_state(monkeypatch):
    fake = _fake_connect(stdout=_build_output(wan_state="4", wan_ip=""))
    monkeypatch.setattr(asyncssh, "connect", fake)

    status = await asus_router_client.get_wan_status(SETTINGS, "test-widget")

    assert status == {"connected": False, "ip": None}


async def test_get_clients_joins_arp_with_leases_and_marks_online(monkeypatch):
    fake = _fake_connect(stdout=_build_output())
    monkeypatch.setattr(asyncssh, "connect", fake)

    clients = await asus_router_client.get_clients(SETTINGS, "test-widget")

    assert {"name": "Laptop", "ip": "192.168.1.10", "online": True} in clients
    assert {"name": "11:22:33:44:55:66", "ip": "192.168.1.11", "online": False} in clients
    assert len(clients) == 2


async def test_get_traffic_reads_wan_interface_counters(monkeypatch):
    fake = _fake_connect(stdout=_build_output(wan_ifname="eth0"))
    monkeypatch.setattr(asyncssh, "connect", fake)

    traffic = await asus_router_client.get_traffic(SETTINGS, "test-widget")

    assert traffic == {"rx_bytes": 1024, "tx_bytes": 512}


async def test_get_traffic_defaults_to_zero_for_unknown_interface(monkeypatch):
    fake = _fake_connect(stdout=_build_output(wan_ifname="vlan99"))
    monkeypatch.setattr(asyncssh, "connect", fake)

    traffic = await asus_router_client.get_traffic(SETTINGS, "test-widget")

    assert traffic == {"rx_bytes": 0, "tx_bytes": 0}


async def test_raises_on_bad_credentials(monkeypatch):
    fake = _fake_connect(connect_error=asyncssh.PermissionDenied("auth failed"))
    monkeypatch.setattr(asyncssh, "connect", fake)

    with pytest.raises(asus_router_client.AsusRouterError, match="username/password"):
        await asus_router_client.test_connection(SETTINGS, "test-widget")


async def test_raises_when_router_unreachable(monkeypatch):
    fake = _fake_connect(connect_error=OSError("no route to host"))
    monkeypatch.setattr(asyncssh, "connect", fake)

    with pytest.raises(asus_router_client.AsusRouterError, match="Could not reach"):
        await asus_router_client.test_connection(SETTINGS, "test-widget")


async def test_raises_when_command_fails(monkeypatch):
    fake = _fake_connect(run_error=asyncssh.Error(0, "channel closed"))
    monkeypatch.setattr(asyncssh, "connect", fake)

    with pytest.raises(asus_router_client.AsusRouterError, match="Could not read status"):
        await asus_router_client.test_connection(SETTINGS, "test-widget")
