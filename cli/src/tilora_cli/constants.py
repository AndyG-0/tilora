"""Shared constants matching deploy/*.sh and the systemd unit names verbatim.

Keep these in lockstep with deploy/tilora-backend.service,
deploy/tilora-frontend.service, and deploy/update.sh — this CLI is meant
to be a drop-in alternative to those scripts, not a divergent reimplementation.
"""

BACKEND_UNIT = "tilora-backend.service"
FRONTEND_UNIT = "tilora-frontend.service"
SERVICE_UNITS = [BACKEND_UNIT, FRONTEND_UNIT]

HEALTH_URL = "http://127.0.0.1:8000/api/health"
HEALTH_CHECK_ATTEMPTS = 30
HEALTH_CHECK_INTERVAL_SECONDS = 2
