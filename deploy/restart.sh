#!/usr/bin/env bash
# Tilora self-restart wrapper.  Granted to the tilora service user via
# /etc/sudoers.d/tilora-restart (written by deploy/install.sh) so that
# the backend process can trigger a service restart without broad sudo
# access.  Only allowed by the exact sudoers rule — do not add any
# functionality here; keep this as a one-liner.
exec systemctl restart tilora-backend.service tilora-frontend.service
