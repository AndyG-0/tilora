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

"Online" status for a client is approximated from ARP table presence
(MAC/IP pairs the router has recently resolved) rather than true wireless
association state — reading `wl`/`dhd` assoc lists is chipset/model
specific enough that it isn't worth the fragility here.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import asyncssh

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
    ("LEASES", "cat /var/lib/misc/dnsmasq.leases 2>/dev/null"),
    ("ARP", "cat /proc/net/arp"),
]
_REMOTE_COMMAND = "; ".join(f"echo @@{name}@@; {cmd}" for name, cmd in _REMOTE_SECTIONS)
_SECTION_MARKER_PATTERN = re.compile(r"@@([A-Z_]+)@@")

# Merlin's documented wan0_state_t value for "connected" (WAN_STOPPED = 0,
# ... WAN_STATE_CONNECTED = 2, ...). The status string equivalent used by
# the old HTTP hook (`wanlink_statusstr`) isn't available over this path.
_WAN_STATE_CONNECTED = "2"


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
    # Settings can round-trip through JSON storage/APIs that don't guarantee
    # `ssh_port` stays a native int (e.g. a stringified "22").
    raw_port = settings.get("ssh_port")
    try:
        return 22 if raw_port in (None, "") else int(raw_port)
    except (TypeError, ValueError):
        return 22


async def _connect(settings: dict[str, Any]) -> asyncssh.SSHClientConnection:
    host = settings.get("host") or ""
    try:
        return await asyncio.wait_for(
            asyncssh.connect(
                host,
                port=_ssh_port(settings),
                username=settings.get("username") or "",
                password=settings.get("password") or "",
                # No host-key pinning — matches this client's existing
                # LAN-only trust model (a home router isn't expected to
                # have a CA-issued SSH host key to verify against).
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
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in output.splitlines():
        match = _SECTION_MARKER_PATTERN.fullmatch(line.strip())
        if match:
            current = match.group(1)
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def _parse_netdev(text: str) -> dict[str, tuple[int, int]]:
    """Parse `/proc/net/dev` into `{iface: (rx_bytes, tx_bytes)}`."""
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


def _parse_leases(text: str) -> dict[str, str]:
    """Parse dnsmasq leases (`<expiry> <mac> <ip> <hostname> <client-id>`) into `{mac: hostname}`."""
    leases: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        mac, hostname = parts[1].lower(), parts[3]
        if hostname and hostname != "*":
            leases[mac] = hostname
    return leases


def _parse_arp(text: str) -> list[tuple[str, str, bool]]:
    """Parse `/proc/net/arp` into `[(mac, ip, online)]` — `online` is a proxy
    from ARP-entry completeness (flag `0x2`), not true wireless association."""
    entries: list[tuple[str, str, bool]] = []
    lines = text.splitlines()
    if lines and lines[0].lower().startswith("ip address"):
        lines = lines[1:]
    for line in lines:
        fields = line.split()
        if len(fields) < 4:
            continue
        ip, flags, mac = fields[0], fields[2], fields[3]
        entries.append((mac.lower(), ip, flags.lower() not in ("0x0", "")))
    return entries


def _parse_clients(arp_text: str, leases_text: str) -> list[dict[str, Any]]:
    leases = _parse_leases(leases_text)
    clients = []
    for mac, ip, online in _parse_arp(arp_text):
        if mac in ("00:00:00:00:00:00", "*", ""):
            continue
        clients.append({"name": leases.get(mac) or mac.upper(), "ip": ip, "online": online})
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
        clients=_parse_clients(sections.get("ARP", ""), sections.get("LEASES", "")),
        rx_bytes=rx_bytes,
        tx_bytes=tx_bytes,
    )
    if use_cache:
        cache.set(cache_key, status, _STATUS_TTL_SECONDS)
    return status


async def test_connection(settings: dict[str, Any], widget_id: str) -> str:
    # Bypasses the cache — this validates not-yet-saved candidate settings
    # (see app/api/asus_router.py), so a stale cached status from the
    # currently-saved connection must never mask bad new credentials.
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
