from __future__ import annotations

from dataclasses import dataclass, field

import asyncssh

from app.plugins.asus_router.plugin import AsusRouterPlugin

CONNECTED_SETTINGS = {
    "host": "router.local",
    "ssh_port": 22,
    "username": "admin",
    "password": "secret",
}


@dataclass
class _FakeCompletedProcess:
    stdout: str


@dataclass
class _FakeConnection:
    stdout: str = ""
    run_error: Exception | None = None
    run_calls: int = field(default=0, init=False)

    async def run(self, command: str, check: bool = False):
        self.run_calls += 1
        if self.run_error is not None:
            raise self.run_error
        return _FakeCompletedProcess(stdout=self.stdout)

    def close(self) -> None:
        pass

    async def wait_closed(self) -> None:
        pass


def _fake_connect(*, stdout: str = "", connect_error: Exception | None = None):
    connection = _FakeConnection(stdout=stdout)

    async def fake_connect(host, *, port, username, password, known_hosts):
        if connect_error is not None:
            raise connect_error
        return connection

    fake_connect.connection = connection
    return fake_connect


def _build_output(
    *,
    wan_state: str = "2",
    wan_ip: str = "203.0.113.5",
    wan_ifname: str = "eth0",
    productid: str = "RT-AX88U",
    online_client: bool = True,
) -> str:
    netdev_lines = [
        "  lo: 100 1 0 0 0 0 0 0 100 1 0 0 0 0 0 0",
        "eth0: 1024 10 0 0 0 0 0 0 512 5 0 0 0 0 0 0",
    ]
    leases_lines = ["1700000000 aa:bb:cc:dd:ee:ff 192.168.1.10 Laptop 01:aa:bb:cc:dd:ee:ff"]
    arp_flag = "0x2" if online_client else "0x0"
    arp_lines = [
        "IP address       HW type     Flags       HW address            Mask     Device",
        f"192.168.1.10     0x1         {arp_flag}         aa:bb:cc:dd:ee:ff     *        br0",
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


def make_plugin(**settings) -> AsusRouterPlugin:
    return AsusRouterPlugin({"id": "asus_router", "settings": {**AsusRouterPlugin.default_settings, **settings}})


async def test_get_summary_when_not_configured():
    plugin = make_plugin(host="")

    summary = await plugin.get_summary()

    assert summary["connected"] is False
    assert summary["wan_connected"] is False
    assert summary["client_count"] == 0
    assert summary["has_password"] is False


async def test_get_summary_masks_password():
    plugin = make_plugin(**CONNECTED_SETTINGS)

    summary = await plugin.get_summary()

    assert "password" not in summary
    assert summary["has_password"] is True


async def test_get_summary_when_connected_reports_wan_and_client_count(monkeypatch):
    monkeypatch.setattr(asyncssh, "connect", _fake_connect(stdout=_build_output()))
    plugin = make_plugin(**CONNECTED_SETTINGS)

    summary = await plugin.get_summary()

    assert summary["connected"] is True
    assert summary["wan_connected"] is True
    assert summary["client_count"] == 1


async def test_get_summary_surfaces_error_without_raising(monkeypatch):
    monkeypatch.setattr(asyncssh, "connect", _fake_connect(connect_error=OSError("refused")))
    plugin = make_plugin(**CONNECTED_SETTINGS)

    summary = await plugin.get_summary()

    assert summary["connected"] is True
    assert "error" in summary
    assert summary["client_count"] == 0


async def test_get_detail_when_not_configured():
    plugin = make_plugin(host="")

    detail = await plugin.get_detail()

    assert detail["connected"] is False
    assert detail["clients"] == []
    assert detail["wan_ip"] is None
    assert detail["rx_bytes"] == 0
    assert detail["tx_bytes"] == 0


async def test_get_detail_when_connected_reports_clients_and_traffic(monkeypatch):
    fake = _fake_connect(stdout=_build_output())
    monkeypatch.setattr(asyncssh, "connect", fake)
    plugin = make_plugin(**CONNECTED_SETTINGS)

    detail = await plugin.get_detail()

    assert detail["connected"] is True
    assert detail["wan_ip"] == "203.0.113.5"
    assert detail["clients"] == [{"name": "Laptop", "ip": "192.168.1.10", "online": True}]
    assert detail["rx_bytes"] == 1024
    assert detail["tx_bytes"] == 512
    # get_detail's wan+clients+traffic reads all land within the same
    # short-lived status cache window, so they share a single SSH round trip.
    assert fake.connection.run_calls == 1


async def test_get_detail_surfaces_wan_error_without_raising(monkeypatch):
    monkeypatch.setattr(asyncssh, "connect", _fake_connect(connect_error=OSError("refused")))
    plugin = make_plugin(**CONNECTED_SETTINGS)

    detail = await plugin.get_detail()

    assert detail["connected"] is True
    assert "error" in detail
    assert detail["clients"] == []
    assert detail["wan_ip"] is None


async def test_get_ai_tools_returns_status_tool():
    plugin = make_plugin(host="")

    tools = plugin.get_ai_tools()

    assert len(tools) == 1
    assert tools[0].name == "get_asus_router_status"
    result = await tools[0].handler()
    assert result["connected"] is False
