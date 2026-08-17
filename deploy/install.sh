#!/usr/bin/env bash
# Installs or upgrades Tilora from the public main branch on apt-based Linux.
set -euo pipefail
IFS=$'\n\t'

readonly REPOSITORY_URL="${TILORA_REPOSITORY_URL:-https://github.com/AndyG-0/tilora.git}"
readonly REPOSITORY_REF="${TILORA_REPOSITORY_REF:-main}"
OS_RELEASE_FILE="${TILORA_OS_RELEASE_FILE:-/etc/os-release}"
readonly NODE_SETUP_URL="https://deb.nodesource.com/setup_24.x"
SYSTEMD_DIR="${TILORA_SYSTEMD_DIR:-/etc/systemd/system}"

INSTALL_USER=""
INSTALL_HOME=""
INSTALL_DIR=""
BACKEND_DIR=""
FRONTEND_DIR=""
INSTALL_KIOSK=""
CUSTOM_API_URL=""

fail() {
  printf 'Tilora install failed: %s\n' "$*" >&2
  exit 1
}

info() {
  printf '\n==> %s\n' "$*"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

parse_args() {
  if [[ -n "${TILORA_KIOSK:-}" ]]; then
    case "$TILORA_KIOSK" in
      1|[Tt][Rr][Uu][Ee]|[Yy][Ee][Ss]|[Yy]) INSTALL_KIOSK=true ;;
      0|[Ff][Aa][Ll][Ss][Ee]|[Nn][Oo]|[Nn]|skip) INSTALL_KIOSK=false ;;
      *) fail "Invalid TILORA_KIOSK value '$TILORA_KIOSK'. Use 'true' or 'false'." ;;
    esac
  fi

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --kiosk)
        INSTALL_KIOSK=true
        shift
        ;;
      --no-kiosk|--server-only|--headless)
        INSTALL_KIOSK=false
        shift
        ;;
      --api-url|--backend-url)
        shift
        [[ $# -gt 0 ]] || fail "Missing argument for $1"
        CUSTOM_API_URL="$1"
        shift
        ;;
      --api-url=*|--backend-url=*)
        CUSTOM_API_URL="${1#*=}"
        shift
        ;;
      -h|--help)
        printf 'Tilora Linux Installer\n\n'
        printf 'Usage: install.sh [options]\n\n'
        printf 'Options:\n'
        printf '  --kiosk           Install Chromium and configure kiosk display autostart\n'
        printf '  --no-kiosk        Install backend and frontend as server-only (headless)\n'
        printf '  --server-only     Alias for --no-kiosk\n'
        printf '  --api-url URL     Set PUBLIC_API_BASE_URL for frontend (default: http://localhost:8000 for kiosk, http://<lan-ip>:8000 for server-only)\n'
        printf '  -h, --help        Show this help message\n\n'
        printf 'Environment variables:\n'
        printf '  TILORA_KIOSK      Set to 1/true for kiosk mode, 0/false for server-only\n'
        printf '  TILORA_INSTALL_DIR Custom install destination (default: ~/tilora)\n'
        printf '  TILORA_PUBLIC_API_BASE_URL Custom frontend backend API URL\n'
        exit 0
        ;;
      *)
        fail "Unknown option '$1'. Use --help for usage."
        ;;
    esac
  done
}

detect_install_user() {
  if [[ "${EUID}" -eq 0 ]]; then
    fail "Run this as the non-root account that should run Tilora; the installer will request sudo when needed."
  fi

  INSTALL_USER="$(id -un)"
  INSTALL_HOME="$(getent passwd "$INSTALL_USER" | cut -d: -f6)"
  [[ -n "$INSTALL_HOME" && -d "$INSTALL_HOME" ]] || fail "Could not determine the home directory for $INSTALL_USER."

  INSTALL_DIR="${TILORA_INSTALL_DIR:-$INSTALL_HOME/tilora}"
  BACKEND_DIR="$INSTALL_DIR/backend"
  FRONTEND_DIR="$INSTALL_DIR/frontend"
}

validate_platform() {
  [[ -r "$OS_RELEASE_FILE" ]] || fail "Cannot read $OS_RELEASE_FILE to identify this Linux distribution."
  # shellcheck disable=SC1090
  source "$OS_RELEASE_FILE"

  local is_debian_like=false
  case "${ID:-}" in
    debian|ubuntu|raspbian|pop|linuxmint|elementary|zorin|armbian|dietpi|devuan|kali|pureos|tuxedo|neon)
      is_debian_like=true
      ;;
    *)
      for like in ${ID_LIKE:-}; do
        if [[ "$like" == "debian" || "$like" == "ubuntu" ]]; then
          is_debian_like=true
          break
        fi
      done
      ;;
  esac

  if [[ "$is_debian_like" != true ]] && command -v apt-get >/dev/null 2>&1; then
    is_debian_like=true
  fi

  if [[ "$is_debian_like" != true ]]; then
    fail "Unsupported distribution '${ID:-unknown}'. Tilora's installer supports Debian, Ubuntu, Raspberry Pi OS, and other Debian-based distributions."
  fi

  case "$(uname -m)" in
    x86_64|aarch64|arm64|armv7l) ;;
    *) fail "Unsupported architecture '$(uname -m)'. Supported: x86_64, aarch64, arm64, armv7l." ;;
  esac
}

install_system_dependencies() {
  info "Installing system dependencies"
  sudo apt-get update
  sudo apt-get install -y ca-certificates curl git build-essential python3

  if ! command -v node >/dev/null 2>&1 || [[ "$(node --version | sed 's/^v//' | cut -d. -f1)" -lt 24 ]]; then
    info "Installing Node.js 24"
    curl -fsSL "$NODE_SETUP_URL" | sudo -E bash -
    sudo apt-get install -y nodejs
  fi
}

install_kiosk_dependencies() {
  info "Installing Chromium and kiosk display dependencies"
  local packages=()
  if apt-cache show chromium-browser >/dev/null 2>&1; then
    packages+=(chromium-browser)
  elif apt-cache show chromium >/dev/null 2>&1; then
    packages+=(chromium)
  fi

  if apt-cache show unclutter >/dev/null 2>&1; then
    packages+=(unclutter)
  fi

  if apt-cache show wlopm >/dev/null 2>&1; then
    packages+=(wlopm)
  fi

  if [[ ${#packages[@]} -gt 0 ]]; then
    sudo apt-get install -y "${packages[@]}"
  else
    info "No chromium or chromium-browser package found in apt repositories. Please install Chromium manually."
  fi
}

configure_kiosk() {
  info "Configuring Chromium kiosk mode"
  local kiosk_script="$INSTALL_DIR/deploy/kiosk.sh"
  chmod 755 "$kiosk_script"

  local policy_dir
  local policy_dirs="${TILORA_CHROME_POLICY_DIRS:-/etc/chromium/policies/managed /etc/opt/chrome/policies/managed /etc/chromium-browser/policies/managed}"
  for policy_dir in $policy_dirs; do
    sudo mkdir -p "$policy_dir"
    local tmp_policy
    tmp_policy="$(mktemp)"
    cat >"$tmp_policy" <<'EOF'
{
  "AudioCaptureAllowedUrls": ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", "http://127.0.0.1:3000"]
}
EOF
    sudo install -m 644 "$tmp_policy" "$policy_dir/tilora.json"
    rm -f "$tmp_policy"
  done

  local autostart_dir="$INSTALL_HOME/.config/autostart"
  mkdir -p "$autostart_dir"
  cat >"$autostart_dir/tilora-kiosk.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Tilora Kiosk
Comment=Start Tilora smart display in kiosk mode
Exec=$kiosk_script
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

  local labwc_dir="$INSTALL_HOME/.config/labwc"
  if [[ -d "$labwc_dir" ]]; then
    local labwc_autostart="$labwc_dir/autostart"
    if [[ ! -f "$labwc_autostart" ]] || ! grep -Fq "$kiosk_script" "$labwc_autostart"; then
      printf '\n# Tilora kiosk display\n%s &\n' "$kiosk_script" >>"$labwc_autostart"
    fi
  fi
}

install_uv() {
  if [[ ! -x "$INSTALL_HOME/.local/bin/uv" ]]; then
    info "Installing uv"
    curl -LsSf https://astral.sh/uv/install.sh | sh
  fi
  export PATH="$INSTALL_HOME/.local/bin:$PATH"
  require_command uv
}

sync_repository() {
  info "Fetching Tilora"
  if [[ -e "$INSTALL_DIR" && ! -d "$INSTALL_DIR/.git" ]]; then
    fail "$INSTALL_DIR already exists but is not a Tilora Git checkout. Move it aside or set TILORA_INSTALL_DIR."
  fi

  if [[ -d "$INSTALL_DIR/.git" ]]; then
    git -C "$INSTALL_DIR" fetch --quiet origin "$REPOSITORY_REF"
    git -C "$INSTALL_DIR" checkout "$REPOSITORY_REF"
    git -C "$INSTALL_DIR" merge --ff-only "origin/$REPOSITORY_REF"
  else
    git clone --branch "$REPOSITORY_REF" --single-branch "$REPOSITORY_URL" "$INSTALL_DIR"
  fi
}

set_env_value() {
  local file="$1"
  local key="$2"
  local value="$3"
  python3 - "$file" "$key" "$value" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
prefix = f"{key}="
lines = path.read_text().splitlines()
for index, line in enumerate(lines):
    if line.startswith(prefix):
        lines[index] = prefix + value
        break
else:
    lines.append(prefix + value)
path.write_text("\n".join(lines) + "\n")
PY
}

detect_system_timezone() {
  local tz=""
  if command -v timedatectl >/dev/null 2>&1; then
    tz="$(timedatectl show -p Timezone --value 2>/dev/null || true)"
  fi
  if [[ -z "$tz" && -f /etc/timezone ]]; then
    tz="$(cat /etc/timezone 2>/dev/null || true)"
  fi
  if [[ -z "$tz" && -L /etc/localtime ]]; then
    tz="$(readlink /etc/localtime 2>/dev/null | sed 's#.*/zoneinfo/##' || true)"
  fi
  printf '%s' "${tz:-UTC}"
}

configure_dashboard() {
  local config_file="$BACKEND_DIR/config/dashboard.yaml"
  local timezone latitude longitude location_name default_tz

  [[ -r /dev/tty ]] || fail "First-run configuration needs an interactive terminal. Run the installer from a terminal session."
  default_tz="$(detect_system_timezone)"
  read -r -p "Timezone [$default_tz]: " timezone </dev/tty
  timezone="${timezone:-$default_tz}"
  read -r -p "Weather latitude: " latitude </dev/tty
  read -r -p "Weather longitude: " longitude </dev/tty
  read -r -p "Weather location name: " location_name </dev/tty

  "$BACKEND_DIR/.venv/bin/python" - "$config_file" "$latitude" "$longitude" "$location_name" <<'PY'
from pathlib import Path
import sys
import yaml

path = Path(sys.argv[1])
config = yaml.safe_load(path.read_text())
weather = next(widget for widget in config["widgets"] if widget["id"] == "weather")
weather["settings"].update(
    latitude=float(sys.argv[2]), longitude=float(sys.argv[3]), location_name=sys.argv[4]
)
path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True))
PY
  set_env_value "$BACKEND_DIR/.env" TIMEZONE "$timezone"
}

configure_ai() {
  local provider model api_key env_key
  read -r -p "AI provider (anthropic, openai, gemini, or skip) [skip]: " provider </dev/tty
  provider="${provider:-skip}"
  case "$provider" in
    skip) return ;;
    anthropic) env_key="ANTHROPIC_API_KEY"; model="anthropic/claude-sonnet-5" ;;
    openai) env_key="OPENAI_API_KEY"; model="openai/gpt-5" ;;
    gemini) env_key="GEMINI_API_KEY"; model="gemini/gemini-2.5-pro" ;;
    *) fail "Unknown AI provider '$provider'. Choose anthropic, openai, gemini, or skip." ;;
  esac

  read -r -p "AI model [$model]: " model </dev/tty
  model="${model:-$model}"
  read -r -s -p "${provider} API key: " api_key </dev/tty
  printf '\n'
  [[ -n "$api_key" ]] || fail "An API key is required when an AI provider is selected."
  set_env_value "$BACKEND_DIR/.env" AI_MODEL "$model"
  set_env_value "$BACKEND_DIR/.env" "$env_key" "$api_key"
}

get_env_value() {
  local file="$1" key="$2"
  if [[ -f "$file" ]]; then
    grep -E "^${key}=" "$file" 2>/dev/null | tail -n 1 | cut -d= -f2- || true
  fi
}

detect_primary_lan_ip() {
  local addresses addr
  addresses="$(hostname -I 2>/dev/null || true)"
  if [[ -n "$addresses" ]]; then
    for addr in $addresses; do
      if [[ "$addr" != *:* && "$addr" != 127.* ]]; then
        printf '%s' "$addr"
        return
      fi
    done
  fi
}

detect_default_api_url() {
  if [[ -n "${CUSTOM_API_URL:-}" ]]; then
    printf '%s' "$CUSTOM_API_URL"
    return
  fi
  if [[ -n "${TILORA_PUBLIC_API_BASE_URL:-}" ]]; then
    printf '%s' "$TILORA_PUBLIC_API_BASE_URL"
    return
  fi
  if [[ "$INSTALL_KIOSK" == true ]]; then
    printf 'http://localhost:8000'
    return
  fi
  local lan_ip
  lan_ip="$(detect_primary_lan_ip)"
  if [[ -n "$lan_ip" ]]; then
    printf 'http://%s:8000' "$lan_ip"
  else
    printf 'http://localhost:8000'
  fi
}

configure_frontend_api() {
  local default_url api_url
  default_url="$(detect_default_api_url)"
  if [[ -n "${CUSTOM_API_URL:-}" || -n "${TILORA_PUBLIC_API_BASE_URL:-}" ]]; then
    api_url="$default_url"
  elif [[ -r /dev/tty && "${TILORA_NONINTERACTIVE:-}" != "true" ]]; then
    read -r -p "Frontend API Base URL [$default_url]: " api_url </dev/tty
    api_url="${api_url:-$default_url}"
  else
    api_url="$default_url"
  fi
  set_env_value "$FRONTEND_DIR/.env" PUBLIC_API_BASE_URL "$api_url"
}

prompt_kiosk_selection() {
  if [[ -n "$INSTALL_KIOSK" ]]; then
    return
  fi
  if [[ -r /dev/tty ]]; then
    local choice
    read -r -p "Configure local Chromium kiosk display on this machine? (y/N) [N]: " choice </dev/tty
    case "$choice" in
      [Yy]|[Yy][Ee][Ss]) INSTALL_KIOSK=true ;;
      *) INSTALL_KIOSK=false ;;
    esac
  else
    INSTALL_KIOSK=false
  fi
}

prepare_configuration() {
  local first_install=false
  if [[ ! -f "$BACKEND_DIR/.env" ]]; then
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    chmod 600 "$BACKEND_DIR/.env"
    first_install=true
  fi
  if [[ ! -f "$BACKEND_DIR/config/dashboard.yaml" ]]; then
    cp "$BACKEND_DIR/config/dashboard.example.yaml" "$BACKEND_DIR/config/dashboard.yaml"
    first_install=true
  fi
  if [[ ! -f "$FRONTEND_DIR/.env" ]]; then
    cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env"
  fi
  chmod 600 "$BACKEND_DIR/.env"
  set_env_value "$BACKEND_DIR/.env" TILORA_INSTALL_METHOD native

  # Ensure PUBLIC_API_BASE_URL has a working value on upgrade or non-interactive installs
  local current_api_url
  current_api_url="$(get_env_value "$FRONTEND_DIR/.env" PUBLIC_API_BASE_URL)"
  if [[ -n "${CUSTOM_API_URL:-}" || -n "${TILORA_PUBLIC_API_BASE_URL:-}" ]]; then
    set_env_value "$FRONTEND_DIR/.env" PUBLIC_API_BASE_URL "$(detect_default_api_url)"
  elif [[ -z "$current_api_url" && "$first_install" != true ]]; then
    set_env_value "$FRONTEND_DIR/.env" PUBLIC_API_BASE_URL "$(detect_default_api_url)"
  fi

  printf '%s' "$first_install"
}

build_application() {
  info "Installing application dependencies"
  (cd "$BACKEND_DIR" && uv sync)
  (cd "$FRONTEND_DIR" && npm ci && npm run build)
}

render_service_units() {
  local service template temporary
  for service in tilora-backend tilora-frontend; do
    template="$INSTALL_DIR/deploy/$service.service"
    temporary="$(mktemp)"
    python3 - "$template" "$temporary" "$INSTALL_USER" "$BACKEND_DIR" "$FRONTEND_DIR" <<'PY'
from pathlib import Path
import sys

template, destination, user, backend, frontend = map(Path, sys.argv[1:])
content = template.read_text()
content = content.replace("__TILORA_USER__", str(user))
content = content.replace("__TILORA_BACKEND_DIR__", str(backend))
content = content.replace("__TILORA_FRONTEND_DIR__", str(frontend))
Path(destination).write_text(content)
PY
    sudo install -m 644 "$temporary" "$SYSTEMD_DIR/$service.service"
    rm -f "$temporary"
  done

  sudo systemctl daemon-reload
  sudo systemctl enable --now tilora-backend.service tilora-frontend.service
}

wait_for_health() {
  info "Waiting for the backend health check"
  for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:8000/api/health >/dev/null; then
      return
    fi
    sleep 2
  done
  sudo systemctl --no-pager --full status tilora-backend.service || true
  fail "The backend did not become healthy. Review the service logs above."
}

print_completion() {
  local addresses addr api_base
  addresses="$(hostname -I 2>/dev/null || true)"
  api_base="$(get_env_value "$FRONTEND_DIR/.env" PUBLIC_API_BASE_URL)"
  printf '\nTilora is running at http://localhost:5173\n'
  if [[ -n "$addresses" ]]; then
    for addr in $addresses; do
      if [[ "$addr" != *:* && "$addr" != 127.* ]]; then
        printf 'LAN access:      http://%s:5173\n' "$addr"
      fi
    done
  fi
  if [[ -n "$api_base" ]]; then
    printf 'Frontend API:    %s\n' "$api_base"
  fi
  printf 'Manage services: sudo systemctl status tilora-backend tilora-frontend\n'
  printf 'View logs:       journalctl -u tilora-backend -u tilora-frontend -f\n'
  printf 'Configuration:   %s/backend/.env, %s/frontend/.env, and %s/backend/config/dashboard.yaml\n' "$INSTALL_DIR" "$INSTALL_DIR" "$INSTALL_DIR"
  if [[ "$INSTALL_KIOSK" == true ]]; then
    printf 'Kiosk mode:      Enabled. Ensure desktop autologin is enabled and reboot (sudo reboot) to start fullscreen.\n'
  else
    printf 'Kiosk mode:      Disabled (server-only). Connect to the dashboard from any browser on your network.\n'
  fi
  printf 'Rerun this installer later to fast-forward, rebuild, and restart Tilora.\n'
}

install_sudoers_restart() {
  local sudoers_file="/etc/sudoers.d/tilora-restart"
  local restart_script="$INSTALL_DIR/deploy/restart.sh"
  # Make the restart wrapper executable.
  chmod 755 "$restart_script"
  # Write a targeted sudoers rule granting only this one script, no-password.
  # visudo -c validates the syntax before it's put in place.
  local tmp_sudoers
  tmp_sudoers="$(mktemp)"
  printf '# Tilora: allow the service user to restart tilora services only.\n' >"$tmp_sudoers"
  printf '%s ALL=(root) NOPASSWD: %s\n' "$INSTALL_USER" "$restart_script" >>"$tmp_sudoers"
  if visudo -c -f "$tmp_sudoers" >/dev/null 2>&1; then
    sudo install -m 440 "$tmp_sudoers" "$sudoers_file"
  else
    rm -f "$tmp_sudoers"
    fail "Generated sudoers file failed validation — not installing."
  fi
  rm -f "$tmp_sudoers"
}

main() {
  parse_args "$@"
  require_command sudo
  sudo -v
  detect_install_user
  validate_platform
  install_system_dependencies
  install_uv
  sync_repository
  local first_install
  first_install="$(prepare_configuration)"
  build_application
  if [[ "$first_install" == true ]]; then
    info "First-run configuration"
    configure_dashboard
    configure_ai
    prompt_kiosk_selection
    configure_frontend_api
  fi
  if [[ "$INSTALL_KIOSK" == true ]]; then
    install_kiosk_dependencies
    configure_kiosk
  fi
  render_service_units
  install_sudoers_restart
  wait_for_health
  print_completion
}

if [[ "${BASH_SOURCE[0]:-}" == "${0:-}" || "${#BASH_SOURCE[@]}" -eq 0 ]]; then
  main "$@"
fi
