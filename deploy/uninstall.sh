#!/usr/bin/env bash
# Uninstalls Tilora native services, sudoers configuration, kiosk policies,
# autostart entries, and optionally removes application files.
set -euo pipefail
IFS=$'\n\t'

SYSTEMD_DIR="${TILORA_SYSTEMD_DIR:-${SYSTEMD_DIR:-/etc/systemd/system}}"
CHROME_POLICY_DIRS="${TILORA_CHROME_POLICY_DIRS:-${CHROME_POLICY_DIRS:-/etc/chromium/policies/managed /etc/opt/chrome/policies/managed /etc/chromium-browser/policies/managed}}"
SUDOERS_FILE="${TILORA_SUDOERS_FILE:-${SUDOERS_FILE:-/etc/sudoers.d/tilora-restart}}"

INSTALL_USER="${INSTALL_USER:-}"
INSTALL_HOME="${INSTALL_HOME:-}"
INSTALL_DIR="${INSTALL_DIR:-}"
KEEP_DATA=false
FORCE=false

fail() {
  printf 'Tilora uninstall failed: %s\n' "$*" >&2
  exit 1
}

info() {
  printf '\n==> %s\n' "$*"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -y|--yes|--force|-f)
        FORCE=true
        shift
        ;;
      --keep-data|--keep-files)
        KEEP_DATA=true
        shift
        ;;
      --purge|--all)
        KEEP_DATA=false
        shift
        ;;
      --install-dir)
        shift
        [[ $# -gt 0 ]] || fail "Missing argument for --install-dir"
        INSTALL_DIR="$1"
        shift
        ;;
      --install-dir=*)
        INSTALL_DIR="${1#*=}"
        shift
        ;;
      -h|--help)
        printf 'Tilora Linux Uninstaller\n\n'
        printf 'Usage: uninstall.sh [options]\n\n'
        printf 'Options:\n'
        printf '  -y, --yes, --force   Non-interactive mode; proceed without prompting\n'
        printf '  --keep-data          Keep configuration files, database, and repository in ~/tilora\n'
        printf '  --purge, --all       Remove all files including the installation directory (default)\n'
        printf '  --install-dir DIR    Custom install directory (default: ~/tilora)\n'
        printf '  -h, --help           Show this help message\n\n'
        printf 'Environment variables:\n'
        printf '  TILORA_INSTALL_DIR   Custom install destination (default: ~/tilora)\n'
        printf '  TILORA_NONINTERACTIVE Set to 1/true to skip confirmation prompts\n'
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
    fail "Run this as the non-root account that owns the Tilora installation; the uninstaller will request sudo when needed."
  fi

  INSTALL_USER="$(id -un)"
  if [[ -z "${INSTALL_HOME:-}" ]]; then
    if command -v getent >/dev/null 2>&1; then
      INSTALL_HOME="$(getent passwd "$INSTALL_USER" 2>/dev/null | cut -d: -f6 || true)"
    fi
    if [[ -z "${INSTALL_HOME:-}" ]]; then
      INSTALL_HOME="${HOME:-}"
    fi
  fi
  [[ -n "$INSTALL_HOME" && -d "$INSTALL_HOME" ]] || fail "Could not determine the home directory for $INSTALL_USER."

  if [[ -z "$INSTALL_DIR" ]]; then
    INSTALL_DIR="${TILORA_INSTALL_DIR:-$INSTALL_HOME/tilora}"
  fi
}

self_relocate_if_needed() {
  if [[ "${TILORA_UNINSTALL_RELOCATED:-}" == "true" ]]; then
    trap 'rm -f "${BASH_SOURCE[0]}" 2>/dev/null || true' EXIT
    return
  fi

  local script_source="${BASH_SOURCE[0]:-}"
  if [[ -n "$script_source" && "$script_source" != "bash" && "$script_source" != "-" && -f "$script_source" ]]; then
    local script_dir script_file
    script_dir="$(cd "$(dirname "$script_source")" 2>/dev/null && pwd)"
    script_file="$script_dir/$(basename "$script_source")"

    if [[ -n "$INSTALL_DIR" && "$script_file" == "$INSTALL_DIR"/* ]]; then
      local tmp_script
      tmp_script="$(mktemp "${TMPDIR:-/tmp}/tilora-uninstall.XXXXXX.sh")"
      cp "$script_file" "$tmp_script"
      chmod 700 "$tmp_script"
      export TILORA_UNINSTALL_RELOCATED=true
      cd "${HOME:-/tmp}"
      exec bash "$tmp_script" "$@"
    fi
  fi

  if [[ -n "$INSTALL_DIR" && "$PWD" == "$INSTALL_DIR"* ]]; then
    cd "${HOME:-/tmp}"
  fi
}

confirm_uninstall() {
  if [[ "$FORCE" == true || "${TILORA_NONINTERACTIVE:-}" == "true" || "${TILORA_NONINTERACTIVE:-}" == "1" ]]; then
    return
  fi

  if [[ -r /dev/tty ]]; then
    printf 'This will remove Tilora services, autostart entries, and sudoers rules.\n'
    if [[ "$KEEP_DATA" == true ]]; then
      printf 'Installation directory (%s) will be KEPT.\n' "$INSTALL_DIR"
    else
      printf 'Installation directory (%s) and all data will be REMOVED.\n' "$INSTALL_DIR"
    fi
    local answer
    read -r -p "Are you sure you want to uninstall Tilora? (y/N) [N]: " answer </dev/tty
    case "$answer" in
      [Yy]|[Yy][Ee][Ss]) ;;
      *)
        printf 'Uninstall cancelled.\n'
        exit 0
        ;;
    esac
  fi
}

stop_and_remove_services() {
  info "Stopping and removing systemd services"
  local service_removed=false

  for service in tilora-backend tilora-frontend; do
    if sudo systemctl is-active --quiet "$service.service" 2>/dev/null; then
      sudo systemctl stop "$service.service" 2>/dev/null || true
    fi
    if sudo systemctl is-enabled --quiet "$service.service" 2>/dev/null; then
      sudo systemctl disable "$service.service" 2>/dev/null || true
    fi
    if [[ -f "$SYSTEMD_DIR/$service.service" ]]; then
      sudo rm -f "$SYSTEMD_DIR/$service.service"
      service_removed=true
    fi
  done

  if [[ "$service_removed" == true ]]; then
    sudo systemctl daemon-reload 2>/dev/null || true
    sudo systemctl reset-failed 2>/dev/null || true
  fi
}

remove_sudoers_rule() {
  if [[ -f "$SUDOERS_FILE" ]]; then
    info "Removing sudoers restart rule"
    sudo rm -f "$SUDOERS_FILE"
  fi
}

remove_kiosk_configuration() {
  info "Removing kiosk autostart and policies"
  local autostart_desktop="$INSTALL_HOME/.config/autostart/tilora-kiosk.desktop"
  if [[ -f "$autostart_desktop" ]]; then
    rm -f "$autostart_desktop"
  fi

  local labwc_autostart="$INSTALL_HOME/.config/labwc/autostart"
  if [[ -f "$labwc_autostart" ]]; then
    local tmp_labwc
    tmp_labwc="$(mktemp)"
    grep -v -E "tilora.*kiosk|kiosk\.sh" "$labwc_autostart" >"$tmp_labwc" || true
    if [[ -s "$tmp_labwc" ]]; then
      cat "$tmp_labwc" >"$labwc_autostart"
    else
      rm -f "$labwc_autostart"
    fi
    rm -f "$tmp_labwc"
  fi

  for policy_dir in $CHROME_POLICY_DIRS; do
    if [[ -f "$policy_dir/tilora.json" ]]; then
      sudo rm -f "$policy_dir/tilora.json"
    fi
  done
}

remove_install_files() {
  if [[ "$KEEP_DATA" == true ]]; then
    info "Preserving installation files at $INSTALL_DIR"
    return
  fi

  if [[ -d "$INSTALL_DIR" ]]; then
    info "Removing installation directory ($INSTALL_DIR)"
    rm -rf "$INSTALL_DIR"
  fi
}

print_completion() {
  printf '\n==> Tilora has been uninstalled.\n'
  if [[ "$KEEP_DATA" == true ]]; then
    printf 'Services and configurations removed. Your files remain at: %s\n' "$INSTALL_DIR"
  else
    printf 'All services, configurations, and application files have been removed.\n'
  fi
}

main() {
  parse_args "$@"
  require_command sudo
  sudo -v
  detect_install_user
  self_relocate_if_needed "$@"
  confirm_uninstall
  stop_and_remove_services
  remove_sudoers_rule
  remove_kiosk_configuration
  remove_install_files
  print_completion
}

if [[ "${BASH_SOURCE[0]:-}" == "${0:-}" || "${#BASH_SOURCE[@]}" -eq 0 ]]; then
  main "$@"
fi
