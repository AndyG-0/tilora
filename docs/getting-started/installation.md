# Native Linux Installation & Kiosk Setup

Tilora provides an automated one-line installer for Debian-based Linux distributions, including **Debian**, **Ubuntu**, **Raspberry Pi OS**, **DietPi**, **Linux Mint**, **Pop!_OS**, and **Armbian**.

---

## One-Line Automated Installation

Sign in as the non-root user that should run Tilora (e.g. the default `pi` or `andy` user with sudo privileges) and run:

```bash
curl -fsSL https://raw.githubusercontent.com/AndyG-0/tilora/main/deploy/install.sh | bash
```

### What the Installer Does

1. Prompts for `sudo` to install host dependencies (`python3-venv`, `git`, `curl`, `ffmpeg` on demand).
2. Clones or fast-forwards the Tilora repository into `~/tilora`.
3. Installs Python packages using `uv` and builds the SvelteKit frontend.
4. Generates initial configuration files (`backend/.env`, `backend/config/dashboard.yaml`, `frontend/.env`).
5. Configures and registers two systemd services: `tilora-backend.service` and `tilora-frontend.service`.
6. (Optional) Sets up a fullscreen Chromium kiosk display with mouse-hiding and screen power management.

---

## Interactive Setup Wizard

On first run, the installer guides you through interactive prompts:

- **Timezone and Weather Coordinates**: Sets your local timezone and latitude/longitude for weather and flight radar tracking.
- **AI Assistant Provider (Optional)**: Choose between Anthropic (Claude), OpenAI (GPT-4o/GPT-5), Google Gemini, or skip to configure later.
- **Installation Mode**:
    - **Server / Headless mode**: Installs backend and frontend services only. Ideal if accessing Tilora across your local network from phones, tablets, or other computers.
    - **Kiosk mode**: Installs Chromium, `unclutter` (cursor hiding), `wlopm` (Wayland display power management), and sets up automatic login and autostart on desktop boot.
- **Frontend API Base URL**: Configures `PUBLIC_API_BASE_URL` (defaults to `http://localhost:8000` for kiosk mode, or auto-detects your primary LAN IP for server mode).

---

## Command-Line Installation Flags

For headless setups, scripted provisioning (Ansible/Cloud-Init), or CI/CD pipelines, you can pass flags non-interactively:

```bash
# Server-only mode (no browser GUI dependencies)
curl -fsSL https://raw.githubusercontent.com/AndyG-0/tilora/main/deploy/install.sh | bash -s -- --no-kiosk

# Dedicated kiosk mode
curl -fsSL https://raw.githubusercontent.com/AndyG-0/tilora/main/deploy/install.sh | bash -s -- --kiosk

# Custom frontend API endpoint
curl -fsSL https://raw.githubusercontent.com/AndyG-0/tilora/main/deploy/install.sh | bash -s -- --api-url http://192.168.1.50:8000
```

You can also control installation using environment variables:

| Environment Variable | Description | Default |
|---|---|---|
| `TILORA_KIOSK` | Set `1` for kiosk mode or `0` for headless server | Auto-detected / Prompt |
| `TILORA_PUBLIC_API_BASE_URL` | Override backend API URL for browser clients | `http://localhost:8000` |
| `TILORA_INSTALL_DIR` | Directory to install Tilora | `~/tilora` |

---

## Managing Native Systemd Services

Tilora runs as two standard systemd user or system services:

```bash
# Check service status
sudo systemctl status tilora-backend tilora-frontend

# Restart services
sudo systemctl restart tilora-backend tilora-frontend

# Stream live service logs
journalctl -u tilora-backend -u tilora-frontend -f
```

---

## Updating Native Installations

You can update Tilora directly from the dashboard: **Settings → Software update → Update now** (admin only).

Or run the update script manually via SSH:

```bash
bash ~/tilora/deploy/update.sh
```

Or via one-liner without a checkout:

```bash
curl -fsSL https://raw.githubusercontent.com/AndyG-0/tilora/main/deploy/update.sh | bash
```

The update script fast-forwards the git repository, applies any backend migrations, rebuilds the frontend, and restarts services with zero data loss.

---

## Uninstallation

To cleanly remove Tilora and disable systemd units:

```bash
bash ~/tilora/deploy/uninstall.sh
```

Flags:
- `--keep-data`: Removes systemd services and autostart entries, but preserves your database, `.env`, and config files in `~/tilora`.
- `-y, --yes, --force`: Non-interactive mode without confirmation prompts.
