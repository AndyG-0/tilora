# Security, Authentication & Network Exposure

This document covers Tilora's authentication architecture, settings tiers, SQLite concurrency, and safe remote access recommendations.

---

## Authentication & Session Architecture

- **Session Cookies**: Logged-in users authenticate via encrypted HTTP-only session cookies stored in SQLite (hashed using PBKDF2/HMAC-SHA256).
- **Settings Authorization**:
    - `Admin` endpoints (`/api/settings`, `/api/admin/*`, `/api/network-settings/*`) require the `admin` role and strictly reject standard members with `HTTP 403 Forbidden`.
    - `Personal` endpoints (`/api/users/me`, personal widget scopes) automatically resolve the calling user via session cookies.
- **PIN Protection**: PINs are hashed before storage in SQLite and prevent casual profile switching on shared touchscreens.

---

## Network Exposure Best Practices

Tilora is designed for **trusted home / local networks (LAN)** and is not intended to be exposed directly to the public internet without an authentication layer.

### Recommended Remote Access

1. **Mesh VPN (Tailscale / WireGuard - Strongly Recommended)**:
    - Install Tailscale on the Tilora host machine (`curl -fsSL https://tailscale.com/install.sh | sh`).
    - Access your dashboard securely from anywhere on your phone, laptop, or tablet without port forwarding.
2. **Authenticating Reverse Proxy (Cloudflare Access / Authelia / Authentik)**:
    - Place Tilora behind an authenticating reverse proxy with TLS termination.
3. **Never Port Forward Directly**:
    - Never expose port 8000 or 5173/3000 directly to the public internet.

---

## Single-Process SQLite Architecture

Tilora runs as a single FastAPI process backed by SQLite with **Write-Ahead Logging (`PRAGMA journal_mode=WAL`)** enabled.
- WAL mode allows concurrent readers and non-blocking background writes.
- Tilora is designed to run as a single backend instance per database file. Do not run multiple horizontally scaled backend containers against the same SQLite file.
