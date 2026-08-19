#!/usr/bin/env bash
# Launches Chromium in kiosk mode against the dashboard frontend.
# Intended to be run by the kiosk-autostart entry described in README.md.
set -euo pipefail

DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:5173}"

# Keep the screen from blanking/sleeping (Wayland/labwc; swap for `xset`
# equivalents if running on X11).
if command -v wlopm >/dev/null 2>&1; then
  wlopm --off '*' >/dev/null 2>&1 || true
fi

# Hide the mouse cursor after inactivity, since this is a touchscreen.
if command -v unclutter >/dev/null 2>&1; then
  unclutter --idle 0.5 --root >/dev/null 2>&1 &
fi

CHROMIUM_BIN="$(command -v chromium-browser || command -v chromium || true)"
if [[ -z "$CHROMIUM_BIN" ]]; then
  printf 'Tilora kiosk error: neither chromium-browser nor chromium was found in PATH.\n' >&2
  exit 1
fi

exec "$CHROMIUM_BIN" \
  --kiosk \
  --incognito \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-pinch \
  --overscroll-history-navigation=0 \
  --check-for-update-interval=31536000 \
  --autoplay-policy=no-user-gesture-required \
  "$DASHBOARD_URL"
