#!/usr/bin/env bash
# Launches Chromium in kiosk mode against the dashboard frontend.
# Intended to be run by the kiosk-autostart entry described in README.md.
set -euo pipefail

DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:5173}"

# Keep the screen from blanking/sleeping (Wayland/labwc; swap for `xset`
# equivalents if running on X11).
wlopm --off '*' >/dev/null 2>&1 || true

# Hide the mouse cursor after inactivity, since this is a touchscreen.
unclutter --idle 0.5 --root &

exec chromium-browser \
  --kiosk \
  --incognito \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-pinch \
  --overscroll-history-navigation=0 \
  --check-for-update-interval=31536000 \
  "$DASHBOARD_URL"
