# Raspberry Pi Kiosk & Touchscreen Guide

Turn any Raspberry Pi 4 or Raspberry Pi 5 with an official 7" touchscreen, HDMI monitor, or smart TV into a dedicated wall-mounted smart display.

---

## Prerequisites & Operating System

- **Recommended OS**: **Raspberry Pi OS (Bookworm, 64-bit)** with Desktop.
- **Display Server**: Wayland with `labwc` (default on Bookworm) or X11.

---

## 1. Automated Kiosk Setup

Run the one-line installer with the kiosk flag:

```bash
curl -fsSL https://raw.githubusercontent.com/AndyG-0/tilora/main/deploy/install.sh | bash -s -- --kiosk
```

### What this installs:
- **`chromium-browser`**: Fullscreen hardware-accelerated kiosk browser.
- **`unclutter`**: Automatically hides the mouse cursor when idle.
- **`wlopm`**: Wayland display power management for automatic screen blanking/wake.
- **Desktop Autostart**: Configures `~/.config/labwc/autostart` to launch `deploy/kiosk.sh`.

---

## 2. Desktop Autologin Configuration

Ensure desktop auto-login is enabled:

```bash
sudo raspi-config
```
1. Select **System Options** → **Boot / Auto Login**.
2. Select **Desktop Autologin** (Console autologin is not sufficient).
3. Select **Finish** and reboot.

---

## 3. Kiosk Autostart Script (`deploy/kiosk.sh`)

The kiosk script runs on graphical session startup:

```bash
#!/usr/bin/env bash
# Hides cursor on idle
unclutter -idle 0.5 -root &

# Launches Chromium in full kiosk mode
chromium-browser \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --autoplay-policy=no-user-gesture-required \
  --check-for-update-interval=31536000 \
  http://localhost:5173
```

---

## 4. Screen Blanking & Sleep Policies

- **Wayland (labwc)**: Uses `wlopm --on \*` and `wlopm --off \*` to turn the screen backlight on/off on a schedule.
- **X11**: Uses `xset s off -dpms` to prevent blanking or `xset dpms force off` to sleep.
