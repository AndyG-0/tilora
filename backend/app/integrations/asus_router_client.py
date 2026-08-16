"""Asus router (AsusWRT/Merlin firmware) SSH client for the Asus Router
plugin.

The router's stock web UI only allows one active login session at a time —
authenticating over HTTP the way a browser tab would meant any second
Tilora backend (or the user's own browser login to the router's admin UI)
would silently kick the others back to the login page. SSH is a separate
login path on Merlin firmware and isn't subject to that same single-session
limit, so any number of Tilora backends can read status concurrently
without stepping on each other or on the router's own web admin UI.

Each poll opens one SSH connection and runs a single batched shell command
that echoes `nvram`/`/proc`/`dnsmasq` output for WAN status, connected
clients, and WAN traffic, all in one round trip (see `_REMOTE_COMMAND`).
The `nvram` key names and file paths here are long-standing, widely used
Merlin conventions (the same ones Home Assistant's `asuswrt` integration
relies on) but aren't formally documented by Asus — treat an unexpected/
empty parse from a real router as a firmware-version quirk to account for
rather than a bug here.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import re
import socket
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import asyncssh
import httpx

from app.storage.cache import cache

_LOGGER = logging.getLogger(__name__)

_STATUS_TTL_SECONDS = 20
_CONNECT_TIMEOUT_SECONDS = 10
_COMMAND_TIMEOUT_SECONDS = 10

# Each command's output is wrapped between an echoed marker line so one SSH
# round trip can gather everything a poll needs instead of opening a new
# connection per data point.
_REMOTE_SECTIONS = [
    ("WAN_STATE", "nvram get wan0_state_t"),
    ("WAN_IP", "nvram get wan0_ipaddr"),
    ("WAN_IFNAME", "nvram get wan0_ifname"),
    ("PRODUCTID", "nvram get productid"),
    ("NETDEV", "cat /proc/net/dev"),
    ("LEASES", "cat /var/lib/misc/dnsmasq.leases /tmp/etc/dnsmasq.leases /tmp/dnsmasq.leases 2>/dev/null"),
    ("ARP", "cat /proc/net/arp"),
    (
        "CLIENTLIST_JSON",
        # `cat`ing all candidate paths at once concatenates them into invalid JSON
        # whenever more than one exists on a given router (observed on AiMesh: both
        # the nested clientlist.json and a flat nmp_client_list are present
        # simultaneously). Take only the first existing, non-empty candidate.
        "for f in /tmp/clientlist.json /tmp/var/clientlist.json /tmp/clientlist_online.json "
        "/tmp/nmp_cl_json.js /tmp/var/nmp_cl_json.js /tmp/nmp_client_list /jffs/nmp_cl_json.js; do "
        '[ -s "$f" ] && { cat "$f"; break; }; done 2>/dev/null',
    ),
    ("CUSTOM_CLIENTLIST", "nvram get custom_clientlist"),
    ("DHCP_STATICLIST", "nvram get dhcp_staticlist"),
    ("MULTIFILTER_MAC", "nvram get MULTIFILTER_MAC"),
    ("MULTIFILTER_ENABLE", "nvram get MULTIFILTER_ENABLE"),
    (
        "NVRAM_VARS",
        'echo "2G_clients=$(nvram get 2G_clients 2>/dev/null)"; '
        'echo "5G_clients=$(nvram get 5G_clients 2>/dev/null)"; '
        'echo "5G2_clients=$(nvram get 5G2_clients 2>/dev/null)"; '
        'echo "6G_clients=$(nvram get 6G_clients 2>/dev/null)"; '
        'echo "wl0_assoc_list=$(nvram get wl0_assoc_list 2>/dev/null)"; '
        'echo "wl1_assoc_list=$(nvram get wl1_assoc_list 2>/dev/null)"; '
        'echo "wl2_assoc_list=$(nvram get wl2_assoc_list 2>/dev/null)"; '
        'echo "wl3_assoc_list=$(nvram get wl3_assoc_list 2>/dev/null)"; '
        'echo "wlan_sta_list=$(nvram get wlan_sta_list 2>/dev/null)"; '
        'echo "nmp_client_list=$(nvram get nmp_client_list 2>/dev/null)"; '
        'echo "wl_ifnames=$(nvram get wl_ifnames 2>/dev/null)"; '
        'echo "lan_ifnames=$(nvram get lan_ifnames 2>/dev/null)"; '
        'echo "wl0_ifnames=$(nvram get wl0_ifnames 2>/dev/null)"; '
        'echo "wl1_ifnames=$(nvram get wl1_ifnames 2>/dev/null)"; '
        'echo "wl2_ifnames=$(nvram get wl2_ifnames 2>/dev/null)"; '
        'echo "wl3_ifnames=$(nvram get wl3_ifnames 2>/dev/null)"',
    ),
    ("BRIDGE_MACS", "brctl showmacs br0 2>/dev/null"),
    (
        "BRIDGE_PORTS",
        "for p in /sys/class/net/br0/brif/*; do "
        '[ -d "$p" ] && echo "$(basename "$p"):$(cat "$p/port_no" 2>/dev/null):'
        '$([ -d "/sys/class/net/$(basename "$p")/wireless" ] && echo 1 || echo 0)"; '
        "done 2>/dev/null",
    ),
    (
        "WLAN_ASSOC",
        'ifaces="$(nvram get wl_ifnames 2>/dev/null) $(nvram get wl0_ifnames 2>/dev/null) '
        "$(nvram get wl1_ifnames 2>/dev/null) $(nvram get wl2_ifnames 2>/dev/null) "
        "$(nvram get wl3_ifnames 2>/dev/null) $(nvram get lan_ifnames 2>/dev/null) "
        "eth1 eth2 eth3 eth4 eth5 eth6 eth7 eth8 wl0 wl1 wl2 wl3 wl0.1 wl0.2 wl1.1 wl1.2 wl2.1 "
        'ra0 ra1 ra2 rax0 rax1 rax2 wlan0 wlan1 wlan2 ath0 ath1 ath2"; '
        'seen=""; '
        "for iface in $ifaces; do "
        '  case " $seen " in *" $iface "*) continue ;; esac; '
        '  seen="$seen $iface"; '
        '  if [ -d "/sys/class/net/$iface" ] || [ -f "/proc/sys/net/ipv4/conf/$iface/forwarding" ]; then '
        '    out="$(wl -i "$iface" assoclist 2>/dev/null || wlc -i "$iface" assoclist 2>/dev/null || '
        'iwinfo "$iface" assoclist 2>/dev/null || iw dev "$iface" station dump 2>/dev/null || '
        'iwpriv "$iface" show stainfo 2>/dev/null || wlanconfig "$iface" list 2>/dev/null)"; '
        '    if [ -n "$out" ]; then '
        '      echo "IFACE:$iface"; '
        '      echo "$out"; '
        "    fi; "
        "  fi; "
        "done 2>/dev/null",
    ),
]
_REMOTE_COMMAND = "; ".join(f"echo @@{name}@@; {cmd}" for name, cmd in _REMOTE_SECTIONS)
_SECTION_MARKER_PATTERN = re.compile(r"@@([A-Z_]+)@@")

# Merlin's documented wan0_state_t value for "connected" (WAN_STOPPED = 0,
# ... WAN_STATE_CONNECTED = 2, ...).
_WAN_STATE_CONNECTED = "2"

# Curated IEEE OUI prefix lookup table for common device manufacturers (lowercase prefix, no colons).
_OUI_VENDORS: dict[str, str] = {
    # Apple
    "000393": "Apple",
    "000502": "Apple",
    "000a27": "Apple",
    "000a95": "Apple",
    "000d93": "Apple",
    "0010fa": "Apple",
    "001124": "Apple",
    "001451": "Apple",
    "0016cb": "Apple",
    "0017f2": "Apple",
    "0019e3": "Apple",
    "001b63": "Apple",
    "001c42": "Apple",
    "001cb3": "Apple",
    "001d4f": "Apple",
    "001e52": "Apple",
    "001ec2": "Apple",
    "001f5b": "Apple",
    "001ff3": "Apple",
    "0021e9": "Apple",
    "002241": "Apple",
    "002312": "Apple",
    "002332": "Apple",
    "00236c": "Apple",
    "0023df": "Apple",
    "002436": "Apple",
    "002500": "Apple",
    "00254b": "Apple",
    "0025bc": "Apple",
    "002608": "Apple",
    "00264a": "Apple",
    "0026b0": "Apple",
    "0026bb": "Apple",
    "28cfda": "Apple",
    "3c0630": "Apple",
    "3cd0f8": "Apple",
    "40a6d9": "Apple",
    "44d884": "Apple",
    "484ba4": "Apple",
    "4860bc": "Apple",
    "4c3275": "Apple",
    "50bc96": "Apple",
    "542696": "Apple",
    "60f81d": "Apple",
    "685b35": "Apple",
    "705681": "Apple",
    "7cd1c3": "Apple",
    "8c8590": "Apple",
    "9027e4": "Apple",
    "9801a7": "Apple",
    "a483e7": "Apple",
    "acde48": "Apple",
    "b817c2": "Apple",
    "bc5436": "Apple",
    "c869cd": "Apple",
    "d0034b": "Apple",
    "dc2b61": "Apple",
    "e4ce8f": "Apple",
    "f01898": "Apple",
    "f40f24": "Apple",
    "f8ffc2": "Apple",
    # Espressif (ESP8266, ESP32 IoT devices)
    "18fe34": "Espressif",
    "240ac4": "Espressif",
    "2462ab": "Espressif",
    "246f28": "Espressif",
    "24a160": "Espressif",
    "24b2de": "Espressif",
    "24dc82": "Espressif",
    "30aea4": "Espressif",
    "3c6105": "Espressif",
    "3c71bf": "Espressif",
    "4022d8": "Espressif",
    "483fda": "Espressif",
    "485519": "Espressif",
    "4c7525": "Espressif",
    "500291": "Espressif",
    "545a05": "Espressif",
    "5caff7": "Espressif",
    "600194": "Espressif",
    "68c63a": "Espressif",
    "70039f": "Espressif",
    "7c9ebd": "Espressif",
    "807d3a": "Espressif",
    "84cca8": "Espressif",
    "84f3eb": "Espressif",
    "9097d5": "Espressif",
    "94b555": "Espressif",
    "a020a6": "Espressif",
    "a4cf12": "Espressif",
    "ac67b2": "Espressif",
    "b4e62d": "Espressif",
    "bcddc2": "Espressif",
    "c44f33": "Espressif",
    "c82b96": "Espressif",
    "cc50e3": "Espressif",
    "d8a01d": "Espressif",
    "dc4f22": "Espressif",
    "e0e2e6": "Espressif",
    "e831cd": "Espressif",
    "ec94cb": "Espressif",
    "f008d1": "Espressif",
    # Raspberry Pi
    "b827eb": "Raspberry Pi",
    "dca632": "Raspberry Pi",
    "e45f01": "Raspberry Pi",
    "28cdc1": "Raspberry Pi",
    "d83add": "Raspberry Pi",
    # Google / Nest
    "001a11": "Google",
    "1c56fe": "Google",
    "20dfb9": "Google",
    "3c5ab4": "Google",
    "546009": "Google",
    "641666": "Google",
    "70ee50": "Google",
    "94ebcd": "Google",
    "a47733": "Google",
    "d86c63": "Google",
    "f40343": "Google",
    "f4f5d8": "Google",
    "f80f41": "Google",
    "64bc0c": "Nest Labs",
    "18b430": "Nest Labs",
    # Amazon
    "00bb3a": "Amazon",
    "0c47c9": "Amazon",
    "18742e": "Amazon",
    "34d270": "Amazon",
    "38f73d": "Amazon",
    "40b4cd": "Amazon",
    "44650d": "Amazon",
    "50dcbc": "Amazon",
    "6837e9": "Amazon",
    "68545a": "Amazon",
    "747548": "Amazon",
    "84d6d0": "Amazon",
    "ac63be": "Amazon",
    "cc6e47": "Amazon",
    "f0272d": "Amazon",
    "fc65de": "Amazon",
    # Samsung
    "0007ab": "Samsung",
    "001247": "Samsung",
    "001599": "Samsung",
    "00166c": "Samsung",
    "001a8a": "Samsung",
    "001de0": "Samsung",
    "002119": "Samsung",
    "0023d7": "Samsung",
    "0024e9": "Samsung",
    "002637": "Samsung",
    "14f42a": "Samsung",
    "244bfe": "Samsung",
    "30074d": "Samsung",
    "380195": "Samsung",
    "444e1a": "Samsung",
    "508569": "Samsung",
    "5c4979": "Samsung",
    "647791": "Samsung",
    "6cf37f": "Samsung",
    "7840e4": "Samsung",
    "842519": "Samsung",
    "94350a": "Samsung",
    "a80c63": "Samsung",
    "bc4486": "Samsung",
    "c4731e": "Samsung",
    "d0176a": "Samsung",
    "e8e5d6": "Samsung",
    "f409d8": "Samsung",
    # Intel
    "0002b3": "Intel",
    "000347": "Intel",
    "000423": "Intel",
    "000c76": "Intel",
    "000e0c": "Intel",
    "001302": "Intel",
    "0013e8": "Intel",
    "001500": "Intel",
    "00166f": "Intel",
    "0018de": "Intel",
    "0019d1": "Intel",
    "001b21": "Intel",
    "001cbf": "Intel",
    "001d09": "Intel",
    "001e67": "Intel",
    "001f3c": "Intel",
    "00216a": "Intel",
    "0022fb": "Intel",
    "002314": "Intel",
    "0024d7": "Intel",
    "0026c7": "Intel",
    "3413e8": "Intel",
    "4851b7": "Intel",
    "4c1d96": "Intel",
    "6805ca": "Intel",
    "701ce7": "Intel",
    "7c5cf8": "Intel",
    "8086f2": "Intel",
    "8c8caa": "Intel",
    "9cb6d0": "Intel",
    "a44cc8": "Intel",
    "c85b76": "Intel",
    "e4a7a0": "Intel",
    # Sony / PlayStation
    "00014a": "Sony",
    "00041f": "Sony",
    "001315": "Sony",
    "0015c1": "Sony",
    "0019c5": "Sony",
    "001d0d": "Sony",
    "0024be": "Sony",
    "00d9d1": "Sony",
    "280dca": "Sony",
    "709e29": "Sony",
    "a8e3ee": "Sony",
    "fc0f4b": "Sony",
    # Microsoft / Xbox
    "000d3a": "Microsoft",
    "00125a": "Microsoft",
    "00155d": "Microsoft (Hyper-V)",
    "0017fa": "Microsoft",
    "002248": "Microsoft",
    "281878": "Microsoft",
    "7cd95c": "Microsoft",
    "dc9840": "Microsoft",
    # TP-Link / Kasa / Tapo
    "003192": "TP-Link",
    "14eb6c": "TP-Link",
    "1c3bf3": "TP-Link",
    "30de4b": "TP-Link",
    "50c7bf": "TP-Link",
    "60a44c": "TP-Link",
    "7405a5": "TP-Link",
    "84d81b": "TP-Link",
    "984827": "TP-Link",
    "a8da0c": "TP-Link",
    "c0c9e3": "TP-Link",
    "e848b8": "TP-Link",
    # Sonos
    "000e58": "Sonos",
    "48a6b8": "Sonos",
    "5cbaa7": "Sonos",
    "7828ca": "Sonos",
    "949f3e": "Sonos",
    "b8e937": "Sonos",
    # Roku
    "000d4b": "Roku",
    "080581": "Roku",
    "20f543": "Roku",
    "2cb05d": "Roku",
    "84ea99": "Roku",
    "ac3a7a": "Roku",
    "b0a737": "Roku",
    "cc6d10": "Roku",
    "d83134": "Roku",
    # Philips / Signify (Hue)
    "001788": "Philips Hue",
    "ecb5fa": "Philips Hue",
    # Synology
    "001132": "Synology",
    # QNAP
    "00089b": "QNAP",
    "245ebb": "QNAP",
    # Asus
    "000c6e": "Asus",
    "000e8c": "Asus",
    "0011d8": "Asus",
    "0015f2": "Asus",
    "0018f3": "Asus",
    "001a92": "Asus",
    "001bfc": "Asus",
    "001d60": "Asus",
    "001e8c": "Asus",
    "002215": "Asus",
    "002354": "Asus",
    "00248c": "Asus",
    "002618": "Asus",
    "04d4c4": "Asus",
    "049226": "Asus",
    "107b44": "Asus",
    "1c872c": "Asus",
    "2c4d54": "Asus",
    "3085a9": "Asus",
    "40167e": "Asus",
    "50465d": "Asus",
    "6045cb": "Asus",
    "704d7b": "Asus",
    "ac9e17": "Asus",
    "d850e6": "Asus",
    # Netgear
    "00095b": "Netgear",
    "000fb5": "Netgear",
    "00146c": "Netgear",
    "00184d": "Netgear",
    "001f33": "Netgear",
    "0024b2": "Netgear",
    "0026f2": "Netgear",
    "20e52a": "Netgear",
    "28c68e": "Netgear",
    "841b5e": "Netgear",
    "9c3dc1": "Netgear",
    "c40415": "Netgear",
    # LG Electronics
    "0005f9": "LG Electronics",
    "001c62": "LG Electronics",
    "001e75": "LG Electronics",
    "001f6b": "LG Electronics",
    "0021fb": "LG Electronics",
    "10f920": "LG Electronics",
    "203d66": "LG Electronics",
    "3cbbaf": "LG Electronics",
    "58a2b5": "LG Electronics",
    "700514": "LG Electronics",
    "88c9d0": "LG Electronics",
    "a823fe": "LG Electronics",
    "c4366c": "LG Electronics",
    # Nintendo
    "0009bf": "Nintendo",
    "001656": "Nintendo",
    "0017ab": "Nintendo",
    "00191d": "Nintendo",
    "001be0": "Nintendo",
    "001f32": "Nintendo",
    "002147": "Nintendo",
    "00224c": "Nintendo",
    "0022aa": "Nintendo",
    "002331": "Nintendo",
    "00241e": "Nintendo",
    "002444": "Nintendo",
    "0024f3": "Nintendo",
    "0025a0": "Nintendo",
    "002659": "Nintendo",
    "70480f": "Nintendo",
    "7cd77b": "Nintendo",
    "98b6e9": "Nintendo",
    "ccfb65": "Nintendo",
    "e84e06": "Nintendo",
    # Tesla
    "4c2c77": "Tesla Motors",
    "98ed5c": "Tesla Motors",
    # Tuya Smart
    "10d561": "Tuya Smart",
    "508a06": "Tuya Smart",
    "70037e": "Tuya Smart",
    "7c25da": "Tuya Smart",
    "84f703": "Tuya Smart",
    "a4c138": "Tuya Smart",
    "d4a651": "Tuya Smart",
}

# Standard common LAN ports to scan when evaluating a client device.
COMMON_SCAN_PORTS: list[int] = [
    80,
    443,
    8080,
    8443,
    8123,
    5000,
    5001,
    3000,
    8000,
    8006,
    8081,
    8096,
    8888,
    9000,
    9090,
    9443,
    32400,
    631,
    22,
    21,
    23,
    53,
    445,
    548,
    1883,
    3389,
    5900,
    9100,
]

PORT_SERVICES: dict[int, str] = {
    80: "HTTP (Web)",
    443: "HTTPS (Secure Web)",
    8080: "HTTP-Alt / Web UI",
    8443: "HTTPS-Alt / Secure Web UI",
    8123: "Home Assistant",
    5000: "Synology DSM / Web",
    5001: "Synology DSM (HTTPS)",
    3000: "Web App / Dashboard",
    8000: "Web Server / Alt",
    8006: "Proxmox VE Web UI",
    8081: "Web Admin / Stream",
    8096: "Jellyfin / Emby Media",
    8888: "Jupyter / Web Admin",
    9000: "Portainer / Web",
    9090: "Prometheus / Cockpit",
    9443: "Portainer (HTTPS)",
    32400: "Plex Media Server",
    631: "CUPS / IPP Printer Web",
    22: "SSH (Secure Shell)",
    21: "FTP (File Transfer)",
    23: "Telnet",
    53: "DNS (Domain Name Service)",
    445: "SMB / Samba File Sharing",
    548: "AFP (Apple File Protocol)",
    1883: "MQTT IoT Broker",
    3389: "RDP (Remote Desktop)",
    5900: "VNC (Remote Desktop)",
    9100: "RAW Network Printer",
}

WEB_PORTS: set[int] = {
    80,
    443,
    8080,
    8443,
    8123,
    5000,
    5001,
    3000,
    8000,
    8006,
    8081,
    8096,
    8888,
    9000,
    9090,
    9443,
    32400,
    631,
}

_TITLE_TAG_PATTERN = re.compile(r"<title[^>]*>([^<]+)</title>", re.IGNORECASE)


class AsusRouterError(Exception):
    """Raised when an Asus router can't be reached or rejects a request."""


@dataclass
class AsusRouterStatus:
    wan_connected: bool
    wan_ip: str | None
    product_id: str
    clients: list[dict[str, Any]] = field(default_factory=list)
    rx_bytes: int = 0
    tx_bytes: int = 0


def is_configured(settings: dict[str, Any]) -> bool:
    return bool(settings.get("host")) and bool(settings.get("username")) and bool(settings.get("password"))


def _ssh_port(settings: dict[str, Any]) -> int:
    raw_port = settings.get("ssh_port")
    try:
        return 22 if raw_port in (None, "") else int(raw_port)
    except (TypeError, ValueError):
        return 22


def _normalize_mac(mac: str) -> str:
    cleaned = re.sub(r"[^0-9a-fA-F]", "", mac).lower()
    if len(cleaned) == 12:
        return ":".join(cleaned[i : i + 2] for i in range(0, 12, 2))
    return mac.lower().strip()


def lookup_vendor(mac: str, existing_vendor: str | None = None) -> str | None:
    if existing_vendor and existing_vendor.strip():
        return existing_vendor.strip()
    cleaned = re.sub(r"[^0-9a-fA-F]", "", mac).lower()
    if len(cleaned) >= 6:
        prefix = cleaned[:6]
        return _OUI_VENDORS.get(prefix)
    return None


async def _connect(settings: dict[str, Any]) -> asyncssh.SSHClientConnection:
    host = settings.get("host") or ""
    try:
        return await asyncio.wait_for(
            asyncssh.connect(
                host,
                port=_ssh_port(settings),
                username=settings.get("username") or "",
                password=settings.get("password") or "",
                known_hosts=None,
            ),
            timeout=_CONNECT_TIMEOUT_SECONDS,
        )
    except asyncssh.PermissionDenied as exc:
        raise AsusRouterError(
            "Router rejected that username/password over SSH — double check the credentials, and that "
            "'Allow Password login' is enabled under the router's SSH settings."
        ) from exc
    except TimeoutError as exc:
        raise AsusRouterError(
            f"Could not reach the router over SSH (timed out after {_CONNECT_TIMEOUT_SECONDS}s) — double "
            "check the host/port and that SSH access is enabled on the router."
        ) from exc
    except (OSError, asyncssh.Error) as exc:
        raise AsusRouterError(f"Could not reach the router over SSH: {exc}") from exc


def _parse_sections(output: str) -> dict[str, str]:
    # Markers are located anywhere in the text rather than required to be alone on
    # their own line: a `cat`'d file with no trailing newline (e.g. a minified
    # clientlist.json) otherwise glues the next `echo @@NAME@@` marker onto its
    # last line, which would silently drop that section and corrupt the previous
    # one with the leftover marker text.
    matches = list(_SECTION_MARKER_PATTERN.finditer(output))
    sections: dict[str, str] = {}
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(output)
        sections[match.group(1)] = output[start:end].strip()
    return sections


def _parse_netdev(text: str) -> dict[str, tuple[int, int]]:
    result: dict[str, tuple[int, int]] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        iface, rest = line.split(":", 1)
        iface = iface.strip()
        fields = rest.split()
        if not iface or len(fields) < 9:
            continue
        try:
            result[iface] = (int(fields[0]), int(fields[8]))
        except ValueError:
            continue
    return result


def _parse_leases(text: str) -> dict[str, dict[str, Any]]:
    leases: dict[str, dict[str, Any]] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        expiry, mac, ip, hostname = parts[0], _normalize_mac(parts[1]), parts[2], parts[3]
        if hostname == "*":
            hostname = ""
        leases[mac] = {
            "ip": ip,
            "hostname": hostname,
            "expiry": expiry,
        }
    return leases


def _parse_arp(text: str) -> list[tuple[str, str, bool]]:
    entries: list[tuple[str, str, bool]] = []
    lines = text.splitlines()
    if lines and lines[0].lower().startswith("ip address"):
        lines = lines[1:]
    for line in lines:
        fields = line.split()
        if len(fields) < 4:
            continue
        ip, flags, mac = fields[0], fields[2], _normalize_mac(fields[3])
        entries.append((mac, ip, flags.lower() not in ("0x0", "")))
    return entries


def _parse_custom_clientlist(text: str) -> dict[str, str]:
    """Parse NVRAM custom_clientlist `<alias>><mac>>...` or `<name>><mac>>...` into `{mac: alias}`."""
    aliases: dict[str, str] = {}
    if not text:
        return aliases
    entries = [entry for entry in text.split("<") if entry.strip()]
    for entry in entries:
        parts = entry.split(">")
        if len(parts) >= 2:
            alias = parts[0].strip()
            mac = _normalize_mac(parts[1])
            if mac and alias:
                aliases[mac] = alias
    return aliases


def _parse_dhcp_staticlist(text: str) -> dict[str, dict[str, Any]]:
    """Parse NVRAM dhcp_staticlist `<mac>><ip>><hostname>...` into `{mac: {ip, hostname, static: True}}`."""
    static_map: dict[str, dict[str, Any]] = {}
    if not text:
        return static_map
    entries = [entry for entry in text.split("<") if entry.strip()]
    for entry in entries:
        parts = entry.split(">")
        if len(parts) >= 2:
            mac = _normalize_mac(parts[0])
            ip = parts[1].strip()
            hostname = parts[2].strip() if len(parts) > 2 else ""
            if mac:
                static_map[mac] = {"ip": ip, "hostname": hostname, "static": True}
    return static_map


def _parse_blocked_macs(mac_text: str, enable_text: str) -> set[str]:
    """Parse Asus parental control / MULTIFILTER list."""
    blocked: set[str] = set()
    if enable_text.strip() not in ("1", "yes", "true", "TRUE"):
        return blocked
    for item in re.split(r"[><\s]+", mac_text):
        mac = _normalize_mac(item)
        if len(mac) == 17 and mac.count(":") == 5:
            blocked.add(mac)
    return blocked


def _parse_nvram_vars(text: str) -> dict[str, Any]:
    """Parse key=value pairs echoed from nvram variables."""
    parsed: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            parsed[k.strip()] = v.strip()

    wireless_macs: dict[str, str] = {}
    wired_macs: set[str] = set()

    for key in ("2G_clients", "wl0_assoc_list", "wl0_clients"):
        for m in re.split(r"[,\s><]+", parsed.get(key, "")):
            mac = _normalize_mac(m)
            if len(mac) == 17 and mac.count(":") == 5:
                wireless_macs[mac] = "2.4GHz"

    for key in ("5G_clients", "wl1_assoc_list", "wl1_clients"):
        for m in re.split(r"[,\s><]+", parsed.get(key, "")):
            mac = _normalize_mac(m)
            if len(mac) == 17 and mac.count(":") == 5:
                wireless_macs[mac] = "5GHz"

    for key in ("5G2_clients", "wl2_assoc_list", "wl2_clients"):
        for m in re.split(r"[,\s><]+", parsed.get(key, "")):
            mac = _normalize_mac(m)
            if len(mac) == 17 and mac.count(":") == 5:
                wireless_macs[mac] = "5GHz-2"

    for key in ("6G_clients", "wl3_assoc_list", "wl3_clients"):
        for m in re.split(r"[,\s><]+", parsed.get(key, "")):
            mac = _normalize_mac(m)
            if len(mac) == 17 and mac.count(":") == 5:
                wireless_macs[mac] = "6GHz"

    for m in re.split(r"[,\s><]+", parsed.get("wlan_sta_list", "")):
        mac = _normalize_mac(m)
        if len(mac) == 17 and mac.count(":") == 5 and mac not in wireless_macs:
            wireless_macs[mac] = "wireless"

    nmp_raw = parsed.get("nmp_client_list", "")
    nmp_entries = [e for e in nmp_raw.split("<") if e.strip()]
    for entry in nmp_entries:
        parts = entry.split(">")
        if len(parts) >= 4:
            mac = _normalize_mac(parts[1])
            is_wl = parts[3].strip()
            if len(mac) == 17 and mac.count(":") == 5:
                if is_wl == "0":
                    wired_macs.add(mac)
                elif is_wl == "1":
                    wireless_macs[mac] = "2.4GHz"
                elif is_wl == "2":
                    wireless_macs[mac] = "5GHz"
                elif is_wl == "3":
                    wireless_macs[mac] = "5GHz-2"
                elif is_wl == "4":
                    wireless_macs[mac] = "6GHz"

    # Extract wireless and wired interface names from NVRAM
    wl_if_str = " ".join(
        [
            parsed.get("wl_ifnames", ""),
            parsed.get("wl0_ifnames", ""),
            parsed.get("wl1_ifnames", ""),
            parsed.get("wl2_ifnames", ""),
            parsed.get("wl3_ifnames", ""),
            parsed.get("wl0_ifname", ""),
            parsed.get("wl1_ifname", ""),
            parsed.get("wl2_ifname", ""),
            parsed.get("wl3_ifname", ""),
        ]
    )
    wireless_ifnames = {iface for iface in wl_if_str.split() if iface}

    lan_if_str = parsed.get("lan_ifnames", "")
    wired_ifnames = {iface for iface in lan_if_str.split() if iface and iface not in wireless_ifnames}

    return {
        "wireless_macs": wireless_macs,
        "wired_macs": wired_macs,
        "wireless_ifnames": wireless_ifnames,
        "wired_ifnames": wired_ifnames,
        "custom_clientlist": parsed.get("custom_clientlist", ""),
        "dhcp_staticlist": parsed.get("dhcp_staticlist", ""),
        "multifilter_mac": parsed.get("MULTIFILTER_MAC", ""),
        "multifilter_enable": parsed.get("MULTIFILTER_ENABLE", ""),
    }


def _parse_bridge_macs_and_ports(
    bridge_macs_text: str,
    bridge_ports_text: str,
    wireless_ifnames: set[str] | None = None,
    wired_ifnames: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Parse bridge port mapping to identify MACs connected on wireless vs wired ports."""
    port_to_iface: dict[str, dict[str, Any]] = {}
    for line in bridge_ports_text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        parts = line.split(":")
        if len(parts) >= 3:
            iface = parts[0].strip()
            raw_port = parts[1].strip()
            try:
                norm_port = str(int(raw_port, 0))
            except (ValueError, TypeError):
                norm_port = raw_port

            is_w = parts[2].strip() == "1"
            if not is_w and (
                (wireless_ifnames and iface in wireless_ifnames)
                or any(iface.startswith(pfx) for pfx in ("wl", "ra", "ath", "wlan", "eth5", "eth6", "eth7"))
            ):
                is_w = True

            is_wired = (
                (wired_ifnames and iface in wired_ifnames)
                or any(iface.startswith(pfx) for pfx in ("eth0", "vlan", "lan"))
            ) and not is_w

            info = {"iface": iface, "is_wireless": is_w, "is_wired": is_wired}
            port_to_iface[norm_port] = info
            port_to_iface[raw_port] = info

    mac_bridge_info: dict[str, dict[str, Any]] = {}
    for line in bridge_macs_text.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2].lower() == "no":
            port_no, mac_str = parts[0], parts[1]
            mac = _normalize_mac(mac_str)
            if len(mac) == 17 and mac.count(":") == 5:
                try:
                    norm_port = str(int(port_no, 0))
                except (ValueError, TypeError):
                    norm_port = port_no
                port_info = port_to_iface.get(
                    norm_port, port_to_iface.get(port_no, {"iface": "", "is_wireless": False, "is_wired": False})
                )
                mac_bridge_info[mac] = port_info

    return mac_bridge_info


def _parse_wlan_assoc(text: str) -> dict[str, dict[str, Any]]:
    """Parse wireless interface association lists from wl/wlc/iw/iwinfo/iwpriv/wlanconfig."""
    wlan_clients: dict[str, dict[str, Any]] = {}
    current_iface = ""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("IFACE:"):
            current_iface = line.split(":", 1)[1].strip()
            continue

        match = re.search(r"([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}", line)
        if match:
            mac = _normalize_mac(match.group(0))
            if len(mac) == 17 and mac.count(":") == 5:
                band = "wireless"
                if any(k in current_iface.lower() for k in ("wl0", "ra0", "wlan0", "eth1", "2g")):
                    band = "2.4GHz"
                elif any(k in current_iface.lower() for k in ("wl1", "rax0", "rai0", "wlan1", "eth2", "5g")):
                    band = "5GHz"
                elif any(k in current_iface.lower() for k in ("wl2", "rax1", "wlan2", "eth3", "5g2")):
                    band = "5GHz-2"
                elif any(k in current_iface.lower() for k in ("wl3", "wlan3", "eth8", "6g")):
                    band = "6GHz"

                rssi = None
                rssi_match = re.search(r"(-[0-9]{2,3})\s*(?:dBm)?", line)
                if rssi_match:
                    try:
                        rssi = int(rssi_match.group(1))
                    except ValueError:
                        pass

                wlan_clients[mac] = {
                    "iface": current_iface,
                    "band": band,
                    "rssi": rssi,
                }
    return wlan_clients


def _aimesh_band_label(key: str) -> str | None:
    """Map an AiMesh clientlist.json band key ("2G", "5G_2", "wired_mac", ...) to
    the same band label vocabulary used elsewhere (2.4GHz/5GHz/5GHz-2/6GHz)."""
    k = key.strip().upper()
    if k.startswith("2G"):
        return "2.4GHz"
    if k.startswith("5G"):
        return "5GHz-2" if k in ("5G_2", "5G2") else "5GHz"
    if k.startswith("6G"):
        return "6GHz"
    return None


def _parse_clientlist_json(text: str) -> dict[str, dict[str, Any]]:
    """Parse AsusWRT / Merlin /tmp/clientlist.json or nmp_cl_json.js recursively."""
    if not text:
        return {}

    results: dict[str, dict[str, Any]] = {}

    def _extract_dict_clients(d: Any, band: str | None = None) -> None:
        if isinstance(d, list):
            for item in d:
                _extract_dict_clients(item, band)
            return

        if not isinstance(d, dict):
            return

        mac = _normalize_mac(d.get("mac") or "")
        if len(mac) == 17 and mac.count(":") == 5 and mac != "00:00:00:00:00:00":
            entry = dict(d)
            if band and not entry.get("band"):
                entry["band"] = band
            results[mac] = entry

        for k, v in d.items():
            k_mac = _normalize_mac(k)
            is_mac_key = len(k_mac) == 17 and k_mac.count(":") == 5 and k_mac != "00:00:00:00:00:00"
            if is_mac_key and isinstance(v, dict):
                # AiMesh's clientlist.json nests as {node_mac: {band: {client_mac:
                # {...}}}}. A node/band container's values are themselves dicts; a
                # real per-client record's fields (ip, rssi, name, ...) are scalars.
                # Only treat a MAC-shaped key as a client record when its value has
                # no nested dicts — otherwise it's a container, so recurse instead.
                if any(isinstance(val, dict) for val in v.values()):
                    _extract_dict_clients(v, band)
                else:
                    entry = {**v, "mac": k_mac}
                    if band and not entry.get("band"):
                        entry["band"] = band
                    results[k_mac] = entry
            elif isinstance(v, (dict, list)):
                _extract_dict_clients(v, _aimesh_band_label(k) or band)

    for block in text.splitlines():
        line = block.strip()
        if not line:
            continue
        if line.startswith("var "):
            parts = line.split("=", 1)
            if len(parts) == 2:
                line = parts[1].rstrip(";").strip()
        try:
            parsed = json.loads(line)
            _extract_dict_clients(parsed)
        except json.JSONDecodeError:
            pass

    if not results:
        cleaned_text = text.strip()
        if cleaned_text.startswith("var "):
            parts = cleaned_text.split("=", 1)
            if len(parts) == 2:
                cleaned_text = parts[1].rstrip(";").strip()
        try:
            parsed = json.loads(cleaned_text)
            _extract_dict_clients(parsed)
        except json.JSONDecodeError:
            pass

    return results


def _parse_clients(
    arp_text: str,
    leases_text: str,
    clientlist_json_text: str = "",
    custom_clientlist_text: str = "",
    dhcp_staticlist_text: str = "",
    multifilter_mac_text: str = "",
    multifilter_enable_text: str = "",
    wlan_assoc_text: str = "",
    nvram_vars_text: str = "",
    bridge_macs_text: str = "",
    bridge_ports_text: str = "",
) -> list[dict[str, Any]]:
    leases = _parse_leases(leases_text)
    arp_entries = _parse_arp(arp_text)
    clientlist_json = _parse_clientlist_json(clientlist_json_text)

    nvram_info = _parse_nvram_vars(nvram_vars_text) if nvram_vars_text else {}
    nvram_wireless_macs = nvram_info.get("wireless_macs", {})
    nvram_wired_macs = nvram_info.get("wired_macs", set())
    wireless_ifnames = nvram_info.get("wireless_ifnames", set())
    wired_ifnames = nvram_info.get("wired_ifnames", set())

    custom_aliases = _parse_custom_clientlist(custom_clientlist_text or nvram_info.get("custom_clientlist", ""))
    static_leases = _parse_dhcp_staticlist(dhcp_staticlist_text or nvram_info.get("dhcp_staticlist", ""))
    blocked_macs = _parse_blocked_macs(
        multifilter_mac_text or nvram_info.get("multifilter_mac", ""),
        multifilter_enable_text or nvram_info.get("multifilter_enable", ""),
    )
    wlan_assoc = _parse_wlan_assoc(wlan_assoc_text)
    bridge_info = (
        _parse_bridge_macs_and_ports(bridge_macs_text, bridge_ports_text, wireless_ifnames, wired_ifnames)
        if bridge_macs_text
        else {}
    )

    known_macs: dict[str, dict[str, Any]] = {}

    # Seed from ARP entries
    for mac, ip, online in arp_entries:
        if mac in ("00:00:00:00:00:00", "*", ""):
            continue
        known_macs[mac] = {
            "mac": mac,
            "ip": ip,
            "online": online,
            "name": "",
        }

    # Add any active DHCP leases
    for mac, lease_info in leases.items():
        if mac in ("00:00:00:00:00:00", "*", ""):
            continue
        if mac not in known_macs:
            known_macs[mac] = {
                "mac": mac,
                "ip": lease_info["ip"],
                "online": True,
                "name": lease_info.get("hostname", ""),
            }
        else:
            if not known_macs[mac].get("name"):
                known_macs[mac]["name"] = lease_info.get("hostname", "")

    # Overlay clientlist.json if present
    for mac, c_info in clientlist_json.items():
        if mac not in known_macs:
            ip = c_info.get("ip") or ""
            if not ip:
                continue
            known_macs[mac] = {
                "mac": mac,
                "ip": ip,
                "online": bool(c_info.get("online", True)),
                "name": c_info.get("name") or c_info.get("nickName") or "",
            }

    clients: list[dict[str, Any]] = []
    for mac, base in known_macs.items():
        ip = base.get("ip", "")
        c_json = clientlist_json.get(mac, {})
        alias = custom_aliases.get(mac) or c_json.get("nickName") or None
        hostname = (
            base.get("name")
            or leases.get(mac, {}).get("hostname")
            or c_json.get("name")
            or static_leases.get(mac, {}).get("hostname")
            or ""
        )
        display_name = alias or hostname or mac.upper()

        connection_type: str = "unknown"
        wireless_band: str | None = None
        rssi: int | None = None
        tx_rate: float | None = None
        rx_rate: float | None = None

        # 1. Check clientlist.json isWL value
        is_wl_val = c_json.get("isWL")
        if is_wl_val is not None:
            if isinstance(is_wl_val, (list, tuple)) and is_wl_val:
                is_wl_val = is_wl_val[0]
            try:
                is_wl_int = int(str(is_wl_val).strip())
                if is_wl_int == 0:
                    connection_type = "wired"
                elif is_wl_int > 0:
                    connection_type = "wireless"
                    if is_wl_int == 1:
                        wireless_band = "2.4GHz"
                    elif is_wl_int == 2:
                        wireless_band = "5GHz"
                    elif is_wl_int == 3:
                        wireless_band = "5GHz-2"
                    elif is_wl_int == 4:
                        wireless_band = "6GHz"
            except (ValueError, TypeError):
                pass

        # 2. Check wlan_assoc table
        if mac in wlan_assoc:
            connection_type = "wireless"
            wireless_band = wlan_assoc[mac].get("band") or wireless_band or "wireless"
            if rssi is None and wlan_assoc[mac].get("rssi") is not None:
                rssi = wlan_assoc[mac]["rssi"]

        # 3. Check NVRAM wireless lists (2G_clients, 5G_clients, etc.)
        if mac in nvram_wireless_macs:
            connection_type = "wireless"
            wireless_band = nvram_wireless_macs[mac] or wireless_band or "wireless"

        # 4. Check NVRAM wired list (nmp_client_list with isWL == 0)
        if connection_type == "unknown" and mac in nvram_wired_macs:
            connection_type = "wired"

        # 5. Check bridge port wireless vs wired determination
        if mac in bridge_info:
            b_info = bridge_info[mac]
            if b_info.get("is_wireless"):
                connection_type = "wireless"
                if not wireless_band:
                    wireless_band = "wireless"
            elif connection_type == "unknown" and (b_info.get("is_wired") or b_info.get("iface")):
                connection_type = "wired"

        # 6. Check RSSI or Tx/Rx indicators from JSON
        # On AiMesh, clientlist.json aggregates each node's *own* radio-scan table,
        # which can retain an rssi/tx/rx reading for a device that's actually wired
        # into a *different* node (any node whose radio can still hear it). The
        # local bridge forwarding table (step 5) reflects the device's actual,
        # current port and is ground truth, so it must not be overridden by this.
        bridge_says_wired = bool(
            mac in bridge_info and bridge_info[mac].get("is_wired") and not bridge_info[mac].get("is_wireless")
        )

        raw_rssi = c_json.get("rssi")
        if not bridge_says_wired and raw_rssi is not None and str(raw_rssi).strip() != "":
            try:
                parsed_rssi = int(raw_rssi)
                if parsed_rssi < 0:
                    rssi = parsed_rssi
                    connection_type = "wireless"
                    if not wireless_band and c_json.get("band"):
                        wireless_band = c_json["band"]
            except (ValueError, TypeError):
                pass

        raw_tx = c_json.get("curTx") or c_json.get("txRate")
        if not bridge_says_wired and raw_tx is not None:
            try:
                tx_rate = float(raw_tx)
                if tx_rate > 0:
                    connection_type = "wireless"
            except (ValueError, TypeError):
                pass

        raw_rx = c_json.get("curRx") or c_json.get("rxRate")
        if not bridge_says_wired and raw_rx is not None:
            try:
                rx_rate = float(raw_rx)
                if rx_rate > 0:
                    connection_type = "wireless"
            except (ValueError, TypeError):
                pass

        # 7. For actively online clients communicating on the local bridge br0:
        # If exhaustive multi-source checks confirm the client is NOT connected to any Wi-Fi radio,
        # it is connected via a physical Ethernet cable (wired).
        if connection_type == "unknown" and base.get("online") is True:
            connection_type = "wired"

        # 8. Mobile & IoT Heuristics
        # If a device is still unknown, or was incorrectly defaulted to wired (e.g. connected to a wired
        # third-party AP, or sleeping so it fell off Wi-Fi lists but stayed in ARP), we can infer it is
        # wireless based on its hostname or vendor MAC OUI.
        lower_name = display_name.lower()
        mobile_keywords = (
            "iphone",
            "ipad",
            "android",
            "galaxy",
            "pixel",
            "kindle",
            "watch",
            "apple-watch",
            "quest",
            "switch",
            "homepod",
        )
        if any(k in lower_name for k in mobile_keywords):
            connection_type = "wireless"
            if not wireless_band:
                wireless_band = "wireless"

        vendor = lookup_vendor(mac, c_json.get("vendor"))
        if vendor in ("Espressif", "Tuya Smart", "Nest Labs", "Amazon", "Roku", "Philips Hue", "Nintendo", "TP-Link"):
            # These manufacturers almost exclusively make Wi-Fi smart home/mobile devices.
            connection_type = "wireless"
            if not wireless_band:
                wireless_band = "wireless"

        # IP assignment type
        ip_type = "dhcp"
        if mac in static_leases or str(c_json.get("ipMethod", "")).lower() in ("static", "manual"):
            ip_type = "static"

        # Internet blocked status
        is_blocked = (
            mac in blocked_macs
            or str(c_json.get("internetMode", "")).lower() == "block"
            or str(c_json.get("internetState", "")).strip() == "0"
        )

        client_obj: dict[str, Any] = {
            "name": display_name,
            "hostname": hostname,
            "alias": alias,
            "ip": ip,
            "mac": mac,
            "online": base.get("online", False),
            "connection_type": connection_type,
            "wireless_band": wireless_band,
            "rssi": rssi,
            "tx_rate": tx_rate,
            "rx_rate": rx_rate,
            "vendor": vendor,
            "ip_type": ip_type,
            "internet_blocked": is_blocked,
        }
        clients.append(client_obj)

    # Sort clients: online first, then by display name
    clients.sort(key=lambda c: (not c["online"], c["name"].lower()))
    return clients


async def _fetch_status(settings: dict[str, Any], widget_id: str, *, use_cache: bool = True) -> AsusRouterStatus:
    cache_key = f"asus_status:{widget_id}"
    if use_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    conn = await _connect(settings)
    try:
        try:
            result = await asyncio.wait_for(conn.run(_REMOTE_COMMAND, check=False), timeout=_COMMAND_TIMEOUT_SECONDS)
        except TimeoutError as exc:
            raise AsusRouterError("Could not read status from the router: command timed out.") from exc
        except (OSError, asyncssh.Error) as exc:
            raise AsusRouterError(f"Could not read status from the router: {exc}") from exc
    finally:
        conn.close()
        await conn.wait_closed()

    stdout = result.stdout if isinstance(result.stdout, str) else ""
    sections = _parse_sections(stdout)
    if not sections:
        _LOGGER.warning("ASUS SSH command returned no parseable sections; raw output[:300]=%r", stdout[:300])

    wan_ifname = sections.get("WAN_IFNAME", "")
    rx_bytes, tx_bytes = _parse_netdev(sections.get("NETDEV", "")).get(wan_ifname, (0, 0))

    status = AsusRouterStatus(
        wan_connected=sections.get("WAN_STATE", "").strip() == _WAN_STATE_CONNECTED,
        wan_ip=sections.get("WAN_IP") or None,
        product_id=sections.get("PRODUCTID") or "Asus Router",
        clients=_parse_clients(
            arp_text=sections.get("ARP", ""),
            leases_text=sections.get("LEASES", ""),
            clientlist_json_text=sections.get("CLIENTLIST_JSON", ""),
            custom_clientlist_text=sections.get("CUSTOM_CLIENTLIST", ""),
            dhcp_staticlist_text=sections.get("DHCP_STATICLIST", ""),
            multifilter_mac_text=sections.get("MULTIFILTER_MAC", ""),
            multifilter_enable_text=sections.get("MULTIFILTER_ENABLE", ""),
            wlan_assoc_text=sections.get("WLAN_ASSOC", ""),
            nvram_vars_text=sections.get("NVRAM_VARS", ""),
            bridge_macs_text=sections.get("BRIDGE_MACS", ""),
            bridge_ports_text=sections.get("BRIDGE_PORTS", ""),
        ),
        rx_bytes=rx_bytes,
        tx_bytes=tx_bytes,
    )
    if use_cache:
        cache.set(cache_key, status, _STATUS_TTL_SECONDS)
    return status


async def test_connection(settings: dict[str, Any], widget_id: str) -> str:
    status = await _fetch_status(settings, widget_id, use_cache=False)
    return status.product_id


async def get_wan_status(settings: dict[str, Any], widget_id: str) -> dict[str, Any]:
    status = await _fetch_status(settings, widget_id)
    return {"connected": status.wan_connected, "ip": status.wan_ip}


async def get_clients(settings: dict[str, Any], widget_id: str) -> list[dict[str, Any]]:
    status = await _fetch_status(settings, widget_id)
    return status.clients


async def get_traffic(settings: dict[str, Any], widget_id: str) -> dict[str, Any]:
    status = await _fetch_status(settings, widget_id)
    return {"rx_bytes": status.rx_bytes, "tx_bytes": status.tx_bytes}


# --- Network Diagnostics & Router Actions ---


def _is_private_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private and not addr.is_loopback and not addr.is_link_local
    except ValueError:
        return False


async def _probe_tcp_port(ip: str, port: int, timeout: float = 0.6) -> bool:
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=timeout)
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, TimeoutError):
        return False


# Shared across every probe call rather than one httpx.AsyncClient per
# attempt — `verify=False`/`follow_redirects=True` are fixed for every call,
# and per-call timeouts are passed via the request's own `timeout=` kwarg,
# so a single pooled client is safe and avoids a fresh TCP handshake for
# each of the (scheme x candidate-port) attempts a client-port scan makes.
_probe_client = httpx.AsyncClient(verify=False, timeout=1.2)


async def _probe_web_service(ip: str, port: int, timeout: float = 1.2) -> tuple[str | None, str | None]:
    for scheme in ("http", "https"):
        url = f"{scheme}://{ip}" if port in (80, 443) else f"{scheme}://{ip}:{port}"
        try:
            resp = await _probe_client.get(url, timeout=timeout, follow_redirects=True)
            if resp.status_code < 500:
                html = resp.text[:4096]
                title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
                page_title = None
                if title_match:
                    raw_title = title_match.group(1).strip()
                    cleaned = re.sub(r"\s+", " ", raw_title)
                    if cleaned and len(cleaned) < 100:
                        page_title = cleaned
                return url, page_title
        except Exception:
            continue
    fallback_url = f"http://{ip}" if port == 80 else f"http://{ip}:{port}"
    return fallback_url, None


async def scan_client_ports(ip: str, target_ports: list[int] | None = None) -> dict[str, Any]:
    """Asynchronously scan common LAN ports and extract service & web details."""
    if not _is_private_ip(ip):
        raise ValueError(f"Invalid or non-private IP address: {ip}")

    ports_to_scan = target_ports if target_ports else COMMON_SCAN_PORTS

    async def _scan_single_port(port: int) -> dict[str, Any] | None:
        is_open = await _probe_tcp_port(ip, port, timeout=0.6)
        if not is_open:
            return None

        service_name = PORT_SERVICES.get(port, f"TCP Port {port}")
        is_web_port = port in WEB_PORTS or "http" in service_name.lower() or "web" in service_name.lower()
        web_url = None
        title = None

        if is_web_port:
            detected_url, page_title = await _probe_web_service(ip, port)
            web_url = detected_url
            title = page_title

        return {
            "port": port,
            "service": service_name,
            "protocol": "tcp",
            "is_web": is_web_port,
            "web_url": web_url,
            "title": title,
        }

    results = await asyncio.gather(*[_scan_single_port(p) for p in ports_to_scan])
    open_ports_info = [r for r in results if r is not None]
    open_ports_info.sort(key=lambda p: p["port"])

    primary_web_url = None
    for p in open_ports_info:
        if p["is_web"] and p.get("web_url"):
            primary_web_url = p["web_url"]
            break

    return {
        "ip": ip,
        "open_ports": open_ports_info,
        "web_url": primary_web_url,
        "scanned_at": datetime.now(UTC).isoformat(),
    }


def _send_udp_magic_packet(mac: str) -> None:
    hw_bytes = bytes.fromhex(mac.replace(":", "").replace("-", ""))
    payload = b"\xff" * 6 + hw_bytes * 16
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(payload, ("255.255.255.255", 9))
        sock.sendto(payload, ("255.255.255.255", 7))


async def send_wake_on_lan(settings: dict[str, Any], mac: str) -> dict[str, Any]:
    norm_mac = _normalize_mac(mac)
    try:
        await asyncio.to_thread(_send_udp_magic_packet, norm_mac)
    except Exception as exc:
        _LOGGER.warning("Local UDP WOL send failed: %s", exc)

    if is_configured(settings):
        try:
            conn = await _connect(settings)
            try:
                cmd = (
                    f"ether-wake -i br0 {norm_mac} 2>/dev/null || "
                    f"wol -i br0 {norm_mac} 2>/dev/null || ether-wake {norm_mac}"
                )
                await asyncio.wait_for(conn.run(cmd, check=False), timeout=5.0)
            finally:
                conn.close()
                await conn.wait_closed()
        except Exception as exc:
            _LOGGER.warning("Router SSH ether-wake execution failed: %s", exc)

    return {"ok": True, "mac": norm_mac, "message": f"Wake-on-LAN packet sent to {norm_mac}"}


async def ping_client(ip: str, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """Test device connectivity and measure latency using ICMP and fallback TCP."""
    if not _is_private_ip(ip):
        raise ValueError(f"Invalid or non-private IP address: {ip}")

    start_time = time.perf_counter()
    alive = False
    latency_ms: float | None = None

    # 1. Try local ICMP ping via system subprocess
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping",
            "-c",
            "1",
            "-W",
            "1000",
            ip,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=1.5)
        if proc.returncode == 0:
            alive = True
            out_str = stdout.decode()
            match = re.search(r"time[=<]\s*([0-9.]+)\s*ms", out_str, re.IGNORECASE)
            if match:
                latency_ms = round(float(match.group(1)), 1)
            else:
                latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
    except Exception:
        pass

    # 2. If not alive and router settings provided, run ping on router over SSH
    if not alive and settings and is_configured(settings):
        try:
            conn = await _connect(settings)
            try:
                r_start = time.perf_counter()
                res = await asyncio.wait_for(
                    conn.run(f"ping -c 1 -W 1 {ip} 2>/dev/null", check=False),
                    timeout=3.0,
                )
                if res.exit_status == 0 and res.stdout:
                    alive = True
                    match = re.search(r"time[=<]\s*([0-9.]+)\s*ms", res.stdout, re.IGNORECASE)
                    if match:
                        latency_ms = round(float(match.group(1)), 1)
                    else:
                        latency_ms = round((time.perf_counter() - r_start) * 1000, 1)
            finally:
                conn.close()
                await conn.wait_closed()
        except Exception:
            pass

    # 3. Fallback TCP probe across common LAN service ports
    if not alive:
        tcp_start = time.perf_counter()
        for port in [80, 443, 22, 445, 53, 8080, 8123, 3000, 8000, 8006, 9000, 5000, 32400]:
            if await _probe_tcp_port(ip, port, timeout=0.3):
                alive = True
                latency_ms = round((time.perf_counter() - tcp_start) * 1000, 1)
                break

    return {
        "ip": ip,
        "alive": alive,
        "latency_ms": latency_ms if alive else None,
    }


async def set_client_alias(settings: dict[str, Any], widget_id: str, mac: str, alias: str) -> dict[str, Any]:
    norm_mac = _normalize_mac(mac)
    alias_clean = alias.strip().replace(">", "").replace("<", "")
    if is_configured(settings):
        conn = await _connect(settings)
        try:
            # Read existing custom_clientlist
            res = await conn.run("nvram get custom_clientlist", check=False)
            existing = res.stdout.strip() if isinstance(res.stdout, str) else ""
            aliases = _parse_custom_clientlist(existing)
            aliases[norm_mac] = alias_clean

            new_val = "".join(f"<{name}>{m}>0>0" for m, name in aliases.items())
            await conn.run(f"nvram set custom_clientlist='{new_val}'", check=False)
            await conn.run("nvram commit", check=False)
        finally:
            conn.close()
            await conn.wait_closed()

    cache.delete(f"asus_status:{widget_id}")
    cache.delete_prefix(f"detail:{widget_id}")
    return {"ok": True, "mac": norm_mac, "alias": alias_clean}


async def set_client_internet_block(
    settings: dict[str, Any], widget_id: str, mac: str, blocked: bool
) -> dict[str, Any]:
    norm_mac = _normalize_mac(mac)
    if is_configured(settings):
        conn = await _connect(settings)
        try:
            # Check / apply iptables rule for instant block without full firewall restart
            if blocked:
                cmd = f"iptables -I FORWARD -m mac --mac-source {norm_mac} -j DROP 2>/dev/null"
            else:
                cmd = f"iptables -D FORWARD -m mac --mac-source {norm_mac} -j DROP 2>/dev/null"
            await conn.run(cmd, check=False)
        finally:
            conn.close()
            await conn.wait_closed()

    cache.delete(f"asus_status:{widget_id}")
    cache.delete_prefix(f"detail:{widget_id}")
    return {"ok": True, "mac": norm_mac, "blocked": blocked}


async def set_dhcp_static_reservation(
    settings: dict[str, Any], widget_id: str, mac: str, ip: str, hostname: str, enabled: bool
) -> dict[str, Any]:
    norm_mac = _normalize_mac(mac)
    ip_clean = ip.strip()
    name_clean = hostname.strip().replace(">", "").replace("<", "")

    if is_configured(settings):
        conn = await _connect(settings)
        try:
            res = await conn.run("nvram get dhcp_staticlist", check=False)
            existing = res.stdout.strip() if isinstance(res.stdout, str) else ""
            static_map = _parse_dhcp_staticlist(existing)

            if enabled:
                static_map[norm_mac] = {"ip": ip_clean, "hostname": name_clean, "static": True}
            else:
                static_map.pop(norm_mac, None)

            new_val = "".join(f"<{m}>{info['ip']}>{info.get('hostname', '')}>" for m, info in static_map.items())
            await conn.run(f"nvram set dhcp_staticlist='{new_val}'", check=False)
            await conn.run("nvram commit", check=False)
            # Signal dnsmasq to reload if available
            await conn.run("killall -HUP dnsmasq 2>/dev/null", check=False)
        finally:
            conn.close()
            await conn.wait_closed()

    cache.delete(f"asus_status:{widget_id}")
    cache.delete_prefix(f"detail:{widget_id}")
    return {"ok": True, "mac": norm_mac, "static": enabled}
