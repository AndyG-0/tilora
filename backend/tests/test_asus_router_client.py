from __future__ import annotations

import json
from dataclasses import dataclass, field

import asyncssh
import pytest

from app.integrations import asus_router_client

SETTINGS = {"host": "router.local", "ssh_port": 22, "username": "admin", "password": "secret"}


@dataclass
class _FakeCompletedProcess:
    stdout: str
    exit_status: int = 0


@dataclass
class _FakeConnection:
    stdout: str = ""
    exit_status: int = 0
    run_error: Exception | None = None
    run_calls: int = field(default=0, init=False)
    closed: bool = field(default=False, init=False)

    async def run(self, command: str, check: bool = False):
        self.run_calls += 1
        if self.run_error is not None:
            raise self.run_error
        return _FakeCompletedProcess(stdout=self.stdout, exit_status=self.exit_status)

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
    clientlist_json: str | None = None,
    custom_clientlist: str = "",
    dhcp_staticlist: str = "",
    multifilter_mac: str = "",
    multifilter_enable: str = "",
    wlan_assoc: str = "",
    nvram_vars: str = "",
    bridge_macs: str = "",
    bridge_ports: str = "",
) -> str:
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
        ("CLIENTLIST_JSON", [clientlist_json or ""]),
        ("CUSTOM_CLIENTLIST", [custom_clientlist]),
        ("DHCP_STATICLIST", [dhcp_staticlist]),
        ("MULTIFILTER_MAC", [multifilter_mac]),
        ("MULTIFILTER_ENABLE", [multifilter_enable]),
        ("WLAN_ASSOC", [wlan_assoc]),
        ("NVRAM_VARS", [nvram_vars]),
        ("BRIDGE_MACS", [bridge_macs]),
        ("BRIDGE_PORTS", [bridge_ports]),
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

    laptop = next(c for c in clients if c["mac"] == "aa:bb:cc:dd:ee:ff")
    assert laptop["name"] == "Laptop"
    assert laptop["ip"] == "192.168.1.10"
    assert laptop["online"] is True

    offline_dev = next(c for c in clients if c["mac"] == "11:22:33:44:55:66")
    assert offline_dev["online"] is False
    assert len(clients) == 2


async def test_get_clients_parses_rich_clientlist_json(monkeypatch):
    client_data = {
        "28:CF:DA:11:22:33": {
            "mac": "28:cf:da:11:22:33",
            "ip": "192.168.1.50",
            "name": "Andy-iPhone",
            "nickName": "Andy's Phone",
            "isWL": 2,
            "rssi": -48,
            "curTx": 866.7,
            "curRx": 866.7,
            "vendor": "Apple",
            "ipMethod": "DHCP",
            "internetMode": "allow",
            "internetState": 1,
        },
        "B8:27:EB:44:55:66": {
            "mac": "b8:27:eb:44:55:66",
            "ip": "192.168.1.100",
            "name": "raspberrypi",
            "nickName": "Home Assistant",
            "isWL": 0,
            "vendor": "",
            "ipMethod": "Static",
            "internetMode": "allow",
        },
    }
    raw_json = json.dumps(client_data)
    fake = _fake_connect(
        stdout=_build_output(
            clientlist_json=raw_json,
            multifilter_mac="28:cf:da:11:22:33",
            multifilter_enable="1",
        )
    )
    monkeypatch.setattr(asyncssh, "connect", fake)

    clients = await asus_router_client.get_clients(SETTINGS, "test-widget")

    iphone = next(c for c in clients if c["mac"] == "28:cf:da:11:22:33")
    assert iphone["name"] == "Andy's Phone"
    assert iphone["alias"] == "Andy's Phone"
    assert iphone["connection_type"] == "wireless"
    assert iphone["wireless_band"] == "5GHz"
    assert iphone["rssi"] == -48
    assert iphone["tx_rate"] == 866.7
    assert iphone["vendor"] == "Apple"
    assert iphone["internet_blocked"] is True

    pi = next(c for c in clients if c["mac"] == "b8:27:eb:44:55:66")
    assert pi["name"] == "Home Assistant"
    assert pi["connection_type"] == "wired"
    assert pi["vendor"] == "Raspberry Pi"
    assert pi["ip_type"] == "static"


async def test_get_clients_detects_wireless_from_nvram_vars(monkeypatch):
    fake = _fake_connect(
        stdout=_build_output(
            arp_lines=[
                "IP address       HW type     Flags       HW address            Mask     Device",
                "192.168.1.15     0x1         0x2         3c:06:30:11:22:33     *        br0",
                "192.168.1.20     0x1         0x2         40:a6:d9:44:55:66     *        br0",
            ],
            nvram_vars=("2G_clients=3c:06:30:11:22:33\n5G_clients=40:a6:d9:44:55:66\n"),
        )
    )
    monkeypatch.setattr(asyncssh, "connect", fake)

    clients = await asus_router_client.get_clients(SETTINGS, "test-widget")

    c2g = next(c for c in clients if c["mac"] == "3c:06:30:11:22:33")
    assert c2g["connection_type"] == "wireless"
    assert c2g["wireless_band"] == "2.4GHz"

    c5g = next(c for c in clients if c["mac"] == "40:a6:d9:44:55:66")
    assert c5g["connection_type"] == "wireless"
    assert c5g["wireless_band"] == "5GHz"


async def test_get_clients_detects_wireless_and_wired_from_nmp_client_list(monkeypatch):
    fake = _fake_connect(
        stdout=_build_output(
            arp_lines=[
                "IP address       HW type     Flags       HW address            Mask     Device",
                "192.168.1.15     0x1         0x2         3c:06:30:11:22:33     *        br0",
                "192.168.1.20     0x1         0x2         40:a6:d9:44:55:66     *        br0",
                "192.168.1.50     0x1         0x0         00:11:32:aa:bb:cc     *        br0",
            ],
            nvram_vars=(
                "nmp_client_list=<SmartPlug>3C:06:30:11:22:33>0>1>6>0>0><DesktopPC>40:A6:D9:44:55:66>0>0>1>0>0>\n"
            ),
        )
    )
    monkeypatch.setattr(asyncssh, "connect", fake)

    clients = await asus_router_client.get_clients(SETTINGS, "test-widget")

    plug = next(c for c in clients if c["mac"] == "3c:06:30:11:22:33")
    assert plug["connection_type"] == "wireless"
    assert plug["wireless_band"] == "2.4GHz"

    pc = next(c for c in clients if c["mac"] == "40:a6:d9:44:55:66")
    assert pc["connection_type"] == "wired"

    offline_nas = next(c for c in clients if c["mac"] == "00:11:32:aa:bb:cc")
    assert offline_nas["connection_type"] == "unknown"


async def test_get_clients_detects_wireless_from_bridge_and_wlan_assoc(monkeypatch):
    fake = _fake_connect(
        stdout=_build_output(
            arp_lines=[
                "IP address       HW type     Flags       HW address            Mask     Device",
                "192.168.1.30     0x1         0x2         18:fe:34:00:11:22     *        br0",
            ],
            wlan_assoc="IFACE:ra0\nStation 18:fe:34:00:11:22 (on ra0) -55 dBm\n",
        )
    )
    monkeypatch.setattr(asyncssh, "connect", fake)

    clients = await asus_router_client.get_clients(SETTINGS, "test-widget")

    esp = next(c for c in clients if c["mac"] == "18:fe:34:00:11:22")
    assert esp["connection_type"] == "wireless"
    assert esp["wireless_band"] == "2.4GHz"
    assert esp["rssi"] == -55


async def test_get_clients_bridge_port_wired_overrides_stale_clientlist_rssi(monkeypatch):
    """AiMesh's clientlist.json can carry an rssi reading for a device from a node
    other than the one it's actually plugged into (any node whose radio can still
    hear it), even while the device sits wired on the bridge. The local bridge
    forwarding table is current, authoritative ground truth and must win."""
    fake = _fake_connect(
        stdout=_build_output(
            arp_lines=[
                "IP address       HW type     Flags       HW address            Mask     Device",
                "192.168.1.40     0x1         0x2         aa:bb:cc:dd:ee:ff     *        br0",
            ],
            clientlist_json=json.dumps({"aa:bb:cc:dd:ee:ff": {"ip": "192.168.1.40", "rssi": "-70"}}),
            bridge_macs="  2\taa:bb:cc:dd:ee:ff\tno\t\t   0.91",
            bridge_ports="eth2:0x2:0",
            nvram_vars="lan_ifnames=eth1 eth2 eth3 eth4\n",
        )
    )
    monkeypatch.setattr(asyncssh, "connect", fake)

    clients = await asus_router_client.get_clients(SETTINGS, "test-widget")

    desk = next(c for c in clients if c["mac"] == "aa:bb:cc:dd:ee:ff")
    assert desk["connection_type"] == "wired"
    assert desk["rssi"] is None


async def test_get_clients_recovers_section_after_marker_with_no_leading_newline(monkeypatch):
    """A `cat`'d file with no trailing newline (e.g. a minified clientlist.json on
    a real router) glues the next `echo @@NAME@@` marker onto its last output line
    instead of the marker landing on its own line. Section parsing must still
    recover the section that follows, and not corrupt the section it's glued to."""
    client_json = json.dumps({"aa:bb:cc:dd:ee:ff": {"ip": "192.168.1.5", "rssi": "-50"}})
    raw = (
        "@@WAN_STATE@@\n2\n"
        "@@WAN_IP@@\n203.0.113.5\n"
        "@@WAN_IFNAME@@\neth0\n"
        "@@PRODUCTID@@\nRT-AX88U\n"
        "@@NETDEV@@\n"
        "  lo: 100 1 0 0 0 0 0 0 100 1 0 0 0 0 0 0\n"
        "eth0: 1024 10 0 0 0 0 0 0 512 5 0 0 0 0 0 0\n"
        "@@LEASES@@\n"
        "@@ARP@@\n"
        "IP address       HW type     Flags       HW address            Mask     Device\n"
        "192.168.1.5      0x1         0x2         aa:bb:cc:dd:ee:ff     *        br0\n"
        # No trailing newline after the JSON, matching real `cat` output of a file
        # with no trailing newline — the next marker lands glued to this line.
        f"@@CLIENTLIST_JSON@@\n{client_json}"
        "@@CUSTOM_CLIENTLIST@@\n<ZenWiFi>aa:bb:cc:dd:ee:ff>0>0>\n"
        "@@DHCP_STATICLIST@@\n"
        "@@MULTIFILTER_MAC@@\n"
        "@@MULTIFILTER_ENABLE@@\n"
        "@@WLAN_ASSOC@@\n"
        "@@NVRAM_VARS@@\n"
        "@@BRIDGE_MACS@@\n"
        "@@BRIDGE_PORTS@@\n"
    )
    fake = _fake_connect(stdout=raw)
    monkeypatch.setattr(asyncssh, "connect", fake)

    clients = await asus_router_client.get_clients(SETTINGS, "test-widget")

    client = next(c for c in clients if c["mac"] == "aa:bb:cc:dd:ee:ff")
    assert client["connection_type"] == "wireless"
    assert client["rssi"] == -50
    assert client["alias"] == "ZenWiFi"


async def test_get_clients_parses_nested_aimesh_clientlist_json(monkeypatch):
    """AiMesh nests clientlist.json as {node_mac: {band: {client_mac: {...}}}}.
    The node MAC itself must not be treated as a phantom client, and the real
    per-client record nested underneath must still be extracted."""
    node_mac = "A0:36:BC:A1:27:D0"
    client_mac = "70:4F:57:A3:A4:17"
    aimesh_json = json.dumps(
        {
            node_mac: {
                "2G_2": {
                    client_mac: {"ip": "192.168.101.44", "rssi": "-60"},
                }
            }
        }
    )
    fake = _fake_connect(
        stdout=_build_output(
            arp_lines=[
                "IP address       HW type     Flags       HW address            Mask     Device",
                "192.168.101.44   0x1         0x2         70:4f:57:a3:a4:17     *        br1",
            ],
            clientlist_json=aimesh_json,
        )
    )
    monkeypatch.setattr(asyncssh, "connect", fake)

    clients = await asus_router_client.get_clients(SETTINGS, "test-widget")

    client = next(c for c in clients if c["mac"] == "70:4f:57:a3:a4:17")
    assert client["connection_type"] == "wireless"
    assert client["rssi"] == -60
    assert client["wireless_band"] == "2.4GHz"

    assert all(c["mac"] != "a0:36:bc:a1:27:d0" for c in clients)


def test_vendor_oui_lookup():
    assert asus_router_client.lookup_vendor("28:cf:da:00:11:22") == "Apple"
    assert asus_router_client.lookup_vendor("18:fe:34:aa:bb:cc") == "Espressif"
    assert asus_router_client.lookup_vendor("b8:27:eb:11:22:33") == "Raspberry Pi"
    assert asus_router_client.lookup_vendor("00:11:32:44:55:66") == "Synology"
    assert asus_router_client.lookup_vendor("00:00:00:00:00:00") is None
    # Prioritizes existing vendor string
    assert asus_router_client.lookup_vendor("28:cf:da:00:11:22", "Custom Brand") == "Custom Brand"


async def test_scan_client_ports_detects_open_web_ports(monkeypatch):
    async def fake_probe_tcp(ip: str, port: int, timeout: float = 0.6) -> bool:
        return port in (80, 8123, 22)

    async def fake_probe_web(ip: str, port: int, timeout: float = 1.2):
        if port == 80:
            return f"http://{ip}", "Router Web Access"
        if port == 8123:
            return f"http://{ip}:8123", "Home Assistant"
        return f"http://{ip}:{port}", None

    monkeypatch.setattr(asus_router_client, "_probe_tcp_port", fake_probe_tcp)
    monkeypatch.setattr(asus_router_client, "_probe_web_service", fake_probe_web)

    result = await asus_router_client.scan_client_ports("192.168.1.50")

    assert result["ip"] == "192.168.1.50"
    ports = {p["port"]: p for p in result["open_ports"]}
    assert 80 in ports
    assert ports[80]["is_web"] is True
    assert ports[80]["title"] == "Router Web Access"
    assert 8123 in ports
    assert ports[8123]["is_web"] is True
    assert ports[8123]["title"] == "Home Assistant"
    assert 22 in ports
    assert ports[22]["is_web"] is False
    assert result["web_url"] == "http://192.168.1.50"


async def test_scan_client_ports_rejects_public_ip():
    with pytest.raises(ValueError, match="Invalid or non-private IP"):
        await asus_router_client.scan_client_ports("8.8.8.8")


async def test_send_wake_on_lan(monkeypatch):
    fake = _fake_connect()
    monkeypatch.setattr(asyncssh, "connect", fake)

    result = await asus_router_client.send_wake_on_lan(SETTINGS, "aa:bb:cc:dd:ee:ff")

    assert result["ok"] is True
    assert result["mac"] == "aa:bb:cc:dd:ee:ff"
    assert fake.connection.run_calls == 1


async def test_ping_client(monkeypatch):
    async def fake_probe_tcp(ip: str, port: int, timeout: float = 0.3) -> bool:
        return port == 80

    monkeypatch.setattr(asus_router_client, "_probe_tcp_port", fake_probe_tcp)

    result = await asus_router_client.ping_client("192.168.1.10")

    assert result["ip"] == "192.168.1.10"
    assert result["alive"] is True
    assert isinstance(result["latency_ms"], float)


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
