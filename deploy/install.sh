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
  case "${ID:-}" in
    debian|ubuntu|raspbian) ;;
    *)
      if [[ ",${ID_LIKE:-}," != *",debian,"* ]]; then
        fail "Unsupported distribution '${ID:-unknown}'. Tilora's installer supports Debian, Ubuntu, and Raspberry Pi OS."
      fi
      ;;
  esac

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

configure_dashboard() {
  local config_file="$BACKEND_DIR/config/dashboard.yaml"
  local timezone latitude longitude location_name

  [[ -r /dev/tty ]] || fail "First-run configuration needs an interactive terminal. Run the installer from a terminal session."
  read -r -p "Timezone [$(cat /etc/timezone 2>/dev/null || printf UTC)]: " timezone </dev/tty
  timezone="${timezone:-$(cat /etc/timezone 2>/dev/null || printf UTC)}"
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
  local attempt
  info "Waiting for the backend health check"
  for attempt in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:8000/api/health >/dev/null; then
      return
    fi
    sleep 2
  done
  sudo systemctl --no-pager --full status tilora-backend.service || true
  fail "The backend did not become healthy. Review the service logs above."
}

print_completion() {
  local addresses
  addresses="$(hostname -I 2>/dev/null || true)"
  printf '\nTilora is running at http://localhost:5173\n'
  [[ -n "$addresses" ]] && printf 'LAN access: http://%s:5173\n' "${addresses%% *}"
  printf 'Manage services: sudo systemctl status tilora-backend tilora-frontend\n'
  printf 'View logs:       journalctl -u tilora-backend -u tilora-frontend -f\n'
  printf 'Configuration:   %s/backend/.env and %s/backend/config/dashboard.yaml\n' "$INSTALL_DIR" "$INSTALL_DIR"
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
  fi
  render_service_units
  install_sudoers_restart
  wait_for_health
  print_completion
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
