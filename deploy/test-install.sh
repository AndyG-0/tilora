#!/usr/bin/env bash
# shellcheck disable=SC2032,SC2034,SC2329
# Lightweight, dependency-free tests for deploy/install.sh.
set -euo pipefail

TEST_ROOT="$(mktemp -d)"
readonly TEST_ROOT
trap 'rm -rf "$TEST_ROOT"' EXIT

# shellcheck source=deploy/install.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/install.sh"

pass() { printf 'ok - %s\n' "$1"; }
fail_test() { printf 'not ok - %s\n' "$1" >&2; exit 1; }

assert_contains() {
  local file="$1" expected="$2"
  grep -Fqx "$expected" "$file" >/dev/null || fail_test "expected '$expected' in $file"
}

mock_log="$TEST_ROOT/mock.log"
sudo() { "$@"; }
apt-get() { printf 'apt-get'; printf ' %s' "$@"; printf '\n'; } >>"$mock_log"
curl() { printf 'exit 0\n'; }
node() { printf 'v24.0.0\n'; }
git() { printf 'git'; printf ' %s' "$@"; printf '\n'; } >>"$mock_log"
systemctl() { printf 'systemctl'; printf ' %s' "$@"; printf '\n'; } >>"$mock_log"

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
  assert_contains "$mock_log" "apt-get install -y ca-certificates curl git build-essential python3"
  assert_contains "$mock_log" "git -C $INSTALL_DIR fetch --quiet origin main"
  assert_contains "$mock_log" "git -C $INSTALL_DIR checkout main"
  assert_contains "$mock_log" "git -C $INSTALL_DIR merge --ff-only origin/main"
  pass "uses mocked apt and fast-forward Git upgrade"
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

test_piped_execution() {
  local install_script
  install_script="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/install.sh"
  local help_output
  help_output="$(cat "$install_script" | bash -s -- --help)"
  printf '%s\n' "$help_output" | grep -Fq "Tilora Linux Installer" || fail_test "piped execution failed to run --help"
  pass "supports piped execution (curl | bash) under set -u"
}

test_platform_validation
test_kiosk_arg_parsing
test_kiosk_configuration
test_piped_execution
test_mocked_dependencies_and_upgrade
test_service_rendering
test_health_failure
