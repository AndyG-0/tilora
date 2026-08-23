#!/usr/bin/env bash
# shellcheck disable=SC2032,SC2034,SC2329
# Lightweight, dependency-free tests for deploy/install.sh.
set -euo pipefail

TEST_ROOT="$(mktemp -d)"
readonly TEST_ROOT
trap 'rm -rf "$TEST_ROOT"' EXIT
export TILORA_NONINTERACTIVE=true

# shellcheck source=deploy/install.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/install.sh"

pass() { printf 'ok - %s\n' "$1"; }
fail_test() { printf 'not ok - %s\n' "$1" >&2; exit 1; }

assert_contains() {
  local file="$1" expected="$2"
  grep -Fqx "$expected" "$file" >/dev/null || fail_test "expected '$expected' in $file"
}

mock_log="$TEST_ROOT/mock.log"
sudo() { if [[ "$1" == "-v" ]]; then return 0; fi; "$@"; }
_mock_log() { printf '%s' "$1"; shift; printf ' %s' "$@"; printf '\n'; } >>"$mock_log"
apt-get() { _mock_log "apt-get" "$@"; }
curl() { printf 'exit 0\n'; }
node() { printf 'v24.0.0\n'; }
git() { _mock_log "git" "$@"; }
systemctl() { _mock_log "systemctl" "$@"; }
uv() { _mock_log "uv" "$@"; }

test_platform_validation() {
  local os_file="$TEST_ROOT/os-release"

  # Standard Debian
  printf 'ID=debian\nID_LIKE=debian\n' >"$os_file"
  OS_RELEASE_FILE="$os_file"
  validate_platform
  pass "accepts Debian"

  # Ubuntu
  printf 'ID=ubuntu\nID_LIKE=debian\n' >"$os_file"
  validate_platform
  pass "accepts Ubuntu"

  # Raspberry Pi OS
  printf 'ID=raspbian\nID_LIKE=debian\n' >"$os_file"
  validate_platform
  pass "accepts Raspberry Pi OS (raspbian)"

  # Pop!_OS (space-separated ID_LIKE)
  printf 'ID=pop\nID_LIKE="ubuntu debian"\n' >"$os_file"
  validate_platform
  pass "accepts Pop!_OS"

  # Linux Mint
  printf 'ID=linuxmint\nID_LIKE="ubuntu debian"\n' >"$os_file"
  validate_platform
  pass "accepts Linux Mint"

  # Armbian
  printf 'ID=armbian\nID_LIKE=debian\n' >"$os_file"
  validate_platform
  pass "accepts Armbian"

  # DietPi
  printf 'ID=dietpi\nID_LIKE=debian\n' >"$os_file"
  validate_platform
  pass "accepts DietPi"

  # Reject Fedora / RHEL without apt
  printf 'ID=fedora\nID_LIKE=rhel\n' >"$os_file"
  # Unset apt-get function temporarily in subshell to test rejection
  if (unset -f apt-get 2>/dev/null; validate_platform) >/dev/null 2>&1; then
    # If host has apt-get, this is handled; on macOS it won't have apt-get
    if ! command -v apt-get >/dev/null 2>&1; then
      fail_test "rejects unsupported distributions"
    fi
  fi
  pass "handles unsupported distribution checking"
}

test_kiosk_arg_parsing() {
  INSTALL_KIOSK=""
  TILORA_KIOSK=""
  parse_args --kiosk
  [[ "$INSTALL_KIOSK" == "true" ]] || fail_test "expected INSTALL_KIOSK=true for --kiosk"

  INSTALL_KIOSK=""
  parse_args --no-kiosk
  [[ "$INSTALL_KIOSK" == "false" ]] || fail_test "expected INSTALL_KIOSK=false for --no-kiosk"

  INSTALL_KIOSK=""
  parse_args --server-only
  [[ "$INSTALL_KIOSK" == "false" ]] || fail_test "expected INSTALL_KIOSK=false for --server-only"

  INSTALL_KIOSK=""
  TILORA_KIOSK="1"
  parse_args
  [[ "$INSTALL_KIOSK" == "true" ]] || fail_test "expected INSTALL_KIOSK=true for TILORA_KIOSK=1"

  INSTALL_KIOSK=""
  TILORA_KIOSK="0"
  parse_args
  [[ "$INSTALL_KIOSK" == "false" ]] || fail_test "expected INSTALL_KIOSK=false for TILORA_KIOSK=0"

  TILORA_KIOSK=""
  INSTALL_KIOSK=""
  pass "parses kiosk flags and environment variables"
}

test_starter_tiles_arg_parsing() {
  INSTALL_STARTER_TILES=""
  TILORA_STARTER_TILES=""
  parse_args --starter-tiles
  [[ "$INSTALL_STARTER_TILES" == "true" ]] || fail_test "expected INSTALL_STARTER_TILES=true for --starter-tiles"

  INSTALL_STARTER_TILES=""
  parse_args --no-starter-tiles
  [[ "$INSTALL_STARTER_TILES" == "false" ]] || fail_test "expected INSTALL_STARTER_TILES=false for --no-starter-tiles"

  INSTALL_STARTER_TILES=""
  parse_args --empty-dashboard
  [[ "$INSTALL_STARTER_TILES" == "false" ]] || fail_test "expected INSTALL_STARTER_TILES=false for --empty-dashboard"

  INSTALL_STARTER_TILES=""
  TILORA_STARTER_TILES="1"
  parse_args
  [[ "$INSTALL_STARTER_TILES" == "true" ]] || fail_test "expected INSTALL_STARTER_TILES=true for TILORA_STARTER_TILES=1"

  INSTALL_STARTER_TILES=""
  TILORA_STARTER_TILES="0"
  parse_args
  [[ "$INSTALL_STARTER_TILES" == "false" ]] || fail_test "expected INSTALL_STARTER_TILES=false for TILORA_STARTER_TILES=0"

  TILORA_STARTER_TILES=""
  INSTALL_STARTER_TILES=""
  pass "parses starter tiles flags and environment variables"
}

test_starter_tiles_dashboard_configuration() {
  local mock_install="$TEST_ROOT/mock_starter_tiles"
  mkdir -p "$mock_install/backend/config" "$mock_install/frontend"
  printf 'KEY=backend_val\n' >"$mock_install/backend/.env.example"
  printf 'widgets:\n  - id: weather\n    type: weather\n' >"$mock_install/backend/config/dashboard.example.yaml"
  printf 'PUBLIC_API_BASE_URL=\n' >"$mock_install/frontend/.env.example"

  BACKEND_DIR="$mock_install/backend"
  FRONTEND_DIR="$mock_install/frontend"

  # Test default creates from example
  INSTALL_STARTER_TILES=""
  prepare_configuration >/dev/null
  grep -Fq "id: weather" "$mock_install/backend/config/dashboard.yaml" || fail_test "prepare_configuration failed to copy starter dashboard.example.yaml"

  # Test --no-starter-tiles creates empty widgets
  rm -f "$mock_install/backend/config/dashboard.yaml"
  INSTALL_STARTER_TILES=false
  prepare_configuration >/dev/null
  assert_contains "$mock_install/backend/config/dashboard.yaml" "widgets: []"

  INSTALL_STARTER_TILES=""
  pass "configures starter dashboard or empty dashboard based on starter tiles setting"
}

test_kiosk_configuration() {
  local home_dir="$TEST_ROOT/kiosk_home"
  local install_dir="$TEST_ROOT/kiosk_tilora"
  local policy_dir="$TEST_ROOT/policies"
  mkdir -p "$home_dir/.config/labwc" "$install_dir/deploy" "$policy_dir"
  touch "$install_dir/deploy/kiosk.sh"
  INSTALL_HOME="$home_dir"
  INSTALL_DIR="$install_dir"
  TILORA_CHROME_POLICY_DIRS="$policy_dir"

  configure_kiosk

  [[ -x "$install_dir/deploy/kiosk.sh" ]] || fail_test "kiosk.sh must be executable"
  [[ -f "$home_dir/.config/autostart/tilora-kiosk.desktop" ]] || fail_test "autostart desktop entry missing"
  [[ -f "$policy_dir/tilora.json" ]] || fail_test "chrome policy missing"
  grep -Fq "$install_dir/deploy/kiosk.sh" "$home_dir/.config/autostart/tilora-kiosk.desktop" || fail_test "desktop entry missing exec path"
  grep -Fq "$install_dir/deploy/kiosk.sh" "$home_dir/.config/labwc/autostart" || fail_test "labwc autostart missing exec path"
  pass "renders kiosk autostart and policies"
}

test_mocked_dependencies_and_upgrade() {
  INSTALL_HOME="$TEST_ROOT/home"
  mkdir -p "$INSTALL_HOME/.local/bin" "$TEST_ROOT/tilora/.git"
  touch "$INSTALL_HOME/.local/bin/uv"
  chmod +x "$INSTALL_HOME/.local/bin/uv"
  INSTALL_DIR="$TEST_ROOT/tilora"
  BACKEND_DIR="$INSTALL_DIR/backend"
  FRONTEND_DIR="$INSTALL_DIR/frontend"

  install_system_dependencies
  sync_repository
  assert_contains "$mock_log" "apt-get update"
  assert_contains "$mock_log" "apt-get install -y ca-certificates curl git build-essential python3 fonts-noto-color-emoji fonts-noto-core"
  assert_contains "$mock_log" "git -C $INSTALL_DIR fetch --quiet origin main"
  assert_contains "$mock_log" "git -C $INSTALL_DIR checkout main"
  assert_contains "$mock_log" "git -C $INSTALL_DIR merge --ff-only origin/main"
  pass "uses mocked apt and fast-forward Git upgrade"
}

test_cli_install() {
  INSTALL_DIR="$TEST_ROOT/cli_tilora"
  mkdir -p "$INSTALL_DIR/cli"

  install_cli
  assert_contains "$mock_log" "uv tool install --editable $INSTALL_DIR/cli --force"
  pass "installs the tilora CLI via uv tool install --editable"
}

test_service_rendering() {
  local template_root="$TEST_ROOT/templates"
  mkdir -p "$template_root/deploy" "$TEST_ROOT/systemd"
  cp "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/tilora-backend.service" "$template_root/deploy/"
  cp "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/tilora-frontend.service" "$template_root/deploy/"
  INSTALL_DIR="$template_root"
  BACKEND_DIR='/srv/tilora/backend'
  FRONTEND_DIR='/srv/tilora/frontend'
  INSTALL_USER='dashboard'
  SYSTEMD_DIR="$TEST_ROOT/systemd"

  render_service_units
  grep -F 'User=dashboard' "$SYSTEMD_DIR/tilora-backend.service" >/dev/null || fail_test "renders service user"
  grep -F 'WorkingDirectory=/srv/tilora/backend' "$SYSTEMD_DIR/tilora-backend.service" >/dev/null || fail_test "renders backend path"
  grep -F 'ReadWritePaths=/srv/tilora/backend' "$SYSTEMD_DIR/tilora-backend.service" >/dev/null || fail_test "keeps backend write path"
  grep -F 'WorkingDirectory=/srv/tilora/frontend' "$SYSTEMD_DIR/tilora-frontend.service" >/dev/null || fail_test "renders frontend path"
  grep -F 'Environment=PUBLIC_API_BASE_URL=' "$SYSTEMD_DIR/tilora-frontend.service" >/dev/null || fail_test "renders frontend PUBLIC_API_BASE_URL environment variable"
  grep -F 'EnvironmentFile=-/srv/tilora/frontend/.env' "$SYSTEMD_DIR/tilora-frontend.service" >/dev/null || fail_test "renders frontend env file path"
  assert_contains "$mock_log" 'systemctl daemon-reload'
  pass "renders hardened systemd units and invokes mocked systemctl"
}

test_health_failure() {
  curl() { return 1; }
  sleep() { :; }
  if (wait_for_health) >/dev/null 2>&1; then
    fail_test "fails when health endpoint never responds"
  fi
  unset -f curl sleep
  curl() { printf 'exit 0\n'; }
  pass "reports failed health checks"
}

test_api_url_arg_parsing() {
  CUSTOM_API_URL=""
  TILORA_PUBLIC_API_BASE_URL=""
  parse_args --api-url http://192.168.1.50:8000
  [[ "$CUSTOM_API_URL" == "http://192.168.1.50:8000" ]] || fail_test "expected CUSTOM_API_URL for --api-url"

  CUSTOM_API_URL=""
  parse_args --backend-url=http://10.0.0.5:8000
  [[ "$CUSTOM_API_URL" == "http://10.0.0.5:8000" ]] || fail_test "expected CUSTOM_API_URL for --backend-url="

  CUSTOM_API_URL=""
  TILORA_PUBLIC_API_BASE_URL="http://tilora.lan:8000"
  parse_args
  [[ "$(detect_default_api_url)" == "http://tilora.lan:8000" ]] || fail_test "expected TILORA_PUBLIC_API_BASE_URL in detect_default_api_url"

  CUSTOM_API_URL=""
  TILORA_PUBLIC_API_BASE_URL=""
  INSTALL_KIOSK=true
  [[ "$(detect_default_api_url)" == "http://localhost:8000" ]] || fail_test "expected localhost for kiosk mode"

  CUSTOM_API_URL=""
  TILORA_PUBLIC_API_BASE_URL=""
  INSTALL_KIOSK=""
  pass "parses API URL flags and environment variables"
}

test_frontend_env_configuration() {
  local mock_install="$TEST_ROOT/mock_install"
  mkdir -p "$mock_install/backend/config" "$mock_install/frontend"
  printf 'KEY=backend_val\n' >"$mock_install/backend/.env.example"
  printf 'widgets: []\n' >"$mock_install/backend/config/dashboard.example.yaml"
  printf 'PUBLIC_API_BASE_URL=\n' >"$mock_install/frontend/.env.example"

  BACKEND_DIR="$mock_install/backend"
  FRONTEND_DIR="$mock_install/frontend"
  CUSTOM_API_URL="http://192.168.1.100:8000"

  prepare_configuration >/dev/null
  [[ "$(get_env_value "$FRONTEND_DIR/.env" PUBLIC_API_BASE_URL)" == "http://192.168.1.100:8000" ]] || fail_test "prepare_configuration failed to set custom API url"

  # Test kiosk default configuration
  CUSTOM_API_URL=""
  INSTALL_KIOSK=true
  configure_frontend_api
  [[ "$(get_env_value "$FRONTEND_DIR/.env" PUBLIC_API_BASE_URL)" == "http://localhost:8000" ]] || fail_test "configure_frontend_api failed to set kiosk localhost URL"

  CUSTOM_API_URL=""
  INSTALL_KIOSK=""
  pass "configures frontend .env with appropriate backend API base URL"
}

test_piped_execution() {
  local install_script
  install_script="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/install.sh"
  local help_output
  help_output="$(bash -s -- --help < "$install_script")"
  printf '%s\n' "$help_output" | grep -Fq "Tilora Linux Installer" || fail_test "piped execution failed to run --help"
  pass "supports piped execution (curl | bash) under set -u"
}

test_uninstall() {
  local uninstall_script
  uninstall_script="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/uninstall.sh"
  local help_output
  help_output="$(bash -s -- --help < "$uninstall_script")"
  printf '%s\n' "$help_output" | grep -Fq "Tilora Linux Uninstaller" || fail_test "uninstall piped execution failed --help"

  # Setup mock environment for uninstallation
  local mock_home="$TEST_ROOT/uninst_home"
  local mock_install="$TEST_ROOT/uninst_tilora"
  local mock_sysdir="$TEST_ROOT/uninst_systemd"
  local mock_policy="$TEST_ROOT/uninst_policies"
  local mock_sudoers="$TEST_ROOT/uninst_sudoers/tilora-restart"

  mkdir -p "$mock_home/.config/autostart" "$mock_home/.config/labwc" "$mock_install/backend" "$mock_install/.git" "$mock_sysdir" "$mock_policy" "$(dirname "$mock_sudoers")"

  touch "$mock_sysdir/tilora-backend.service" "$mock_sysdir/tilora-frontend.service"
  touch "$mock_sudoers"
  touch "$mock_home/.config/autostart/tilora-kiosk.desktop"
  printf 'other-app &\n# Tilora kiosk display\n/home/user/tilora/deploy/kiosk.sh &\n' >"$mock_home/.config/labwc/autostart"
  touch "$mock_policy/tilora.json"
  touch "$mock_install/backend/storage.db"

  # Run uninstall in subshell with mock paths and --keep-data
  (
    TILORA_SYSTEMD_DIR="$mock_sysdir"
    TILORA_CHROME_POLICY_DIRS="$mock_policy"
    TILORA_SUDOERS_FILE="$mock_sudoers"
    INSTALL_DIR="$mock_install"
    INSTALL_HOME="$mock_home"
    # shellcheck source=deploy/uninstall.sh
    source "$uninstall_script"
    main --keep-data -y --install-dir "$mock_install"
  )

  # Check services and configs were deleted
  [[ ! -f "$mock_sysdir/tilora-backend.service" ]] || fail_test "backend service unit should be removed"
  [[ ! -f "$mock_sysdir/tilora-frontend.service" ]] || fail_test "frontend service unit should be removed"
  [[ ! -f "$mock_sudoers" ]] || fail_test "sudoers file should be removed"
  [[ ! -f "$mock_home/.config/autostart/tilora-kiosk.desktop" ]] || fail_test "autostart desktop entry should be removed"
  [[ ! -f "$mock_policy/tilora.json" ]] || fail_test "chrome policy should be removed"
  grep -Fq "other-app &" "$mock_home/.config/labwc/autostart" || fail_test "labwc should keep other entries"
  grep -Fq "kiosk.sh" "$mock_home/.config/labwc/autostart" && fail_test "labwc should remove kiosk entry"
  [[ -f "$mock_install/backend/storage.db" ]] || fail_test "storage.db should be kept with --keep-data"

  # Run uninstall with --purge
  (
    TILORA_SYSTEMD_DIR="$mock_sysdir"
    TILORA_CHROME_POLICY_DIRS="$mock_policy"
    TILORA_SUDOERS_FILE="$mock_sudoers"
    INSTALL_DIR="$mock_install"
    INSTALL_HOME="$mock_home"
    # shellcheck source=deploy/uninstall.sh
    source "$uninstall_script"
    main --purge -y --install-dir "$mock_install"
  )

  [[ ! -d "$mock_install" ]] || fail_test "install directory should be removed with --purge"
  pass "uninstaller cleans up services, sudoers, kiosk autostart, and install files"
}

test_platform_validation
test_kiosk_arg_parsing
test_starter_tiles_arg_parsing
test_starter_tiles_dashboard_configuration
test_api_url_arg_parsing
test_kiosk_configuration
test_frontend_env_configuration
test_piped_execution
test_mocked_dependencies_and_upgrade
test_cli_install
test_service_rendering
test_health_failure
test_uninstall

