#!/usr/bin/env bash
# Lightweight, dependency-free tests for deploy/install.sh.
set -euo pipefail

readonly TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

# shellcheck source=install.sh
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
  printf 'ID=debian\nID_LIKE=debian\n' >"$os_file"
  OS_RELEASE_FILE="$os_file"
  validate_platform
  pass "accepts Debian-family releases"

  printf 'ID=fedora\nID_LIKE=rhel\n' >"$os_file"
  if (validate_platform) >/dev/null 2>&1; then
    fail_test "rejects unsupported distributions"
  fi
  pass "rejects unsupported distributions"
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

test_platform_validation
test_mocked_dependencies_and_upgrade
test_service_rendering
test_health_failure
