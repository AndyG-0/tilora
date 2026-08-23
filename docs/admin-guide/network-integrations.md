# Network Integrations & Service Credentials

Tilora provides centralized, admin-controlled credentials management for all shared home network services and local appliances.

Credentials configured here are stored encrypted in the backend's local SQLite database and are never returned in plain text over the API.

---

## Centralized Network Integrations

Navigate to **Settings → Admin settings**:

### 1. Pi-hole DNS Sinkhole
- **Host**: `pi.hole` or LAN IP (e.g. `192.168.1.2`).
- **Port**: `80` (or `443` if HTTPS enabled).
- **Password / App Password**: Your Pi-hole web interface admin password or API application token.
- **Test Connection**: Tap **Test connection** to verify connectivity with the Pi-hole v6 FTL engine.

### 2. Jellyfin Media Server
- **Host**: `jellyfin.local` or LAN IP.
- **Port**: `8096`.
- **Authentication Mode**:
    - **API Key (Server-wide)**: Generate an API key in *Jellyfin Dashboard → API Keys*.
    - **Username & Password**: Authenticate with a standard Jellyfin user account.
- **Test Connection**: Validates API authentication and retrieves server library counts.

### 3. Synology NAS
- **Host**: `synology.local` or LAN IP.
- **Port**: `5000` (HTTP) or `5001` (HTTPS).
- **Username & Password**: Synology DSM user account credentials (read permissions for storage manager recommended).
- **Test Connection**: Connects and checks storage volume status.

### 4. Asus Router (SSH)
- **Host**: `router.asus.com` or `192.168.50.1`.
- **SSH Port**: `22`.
- **Username & Password**: Router admin credentials. (Ensure SSH access is enabled in Asuswrt).
- **Test Connection**: Connects via `asyncssh` and verifies command execution.

### 5. HDHomeRun Tuner & DVR
- **Tuner Host & Port**: IP address of your HDHomeRun tuner (default port `80`).
- **DVR Host & Port**: Optional IP address of your HDHomeRun DVR recording engine (default port `59090`).
- **XMLTV Guide URL**: Optional custom EPG guide URL.
- **Test Connection**: Queries device discovery and tuner channel lineup.
