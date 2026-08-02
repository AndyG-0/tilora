#!/bin/sh
set -e

# A bind-mounted host file that doesn't exist yet becomes an empty directory
# inside the container (Docker's default behavior for a missing bind-mount
# source). Left unhandled, that turns into either a silently-empty config
# (pydantic-settings quietly skips a directory where it expects `.env`) or an
# opaque IsADirectoryError deep in a Python traceback (dashboard.yaml) —
# instead of a clear, actionable failure. Catch it here.
if [ -d /app/.env ]; then
    echo "ERROR: /app/.env is a directory, not a file." >&2
    echo "This usually means backend/.env was never created on the host before starting Docker." >&2
    echo "Run 'cp backend/.env.example backend/.env', then restart the container." >&2
    exit 1
fi

# dashboard.yaml is mounted via a directory bind-mount (./backend/config),
# so a missing file here is a normal missing file, not a phantom directory —
# safe to just fill in from the example that ships in the image.
if [ ! -e /app/config/dashboard.yaml ] && [ -f /app/config/dashboard.example.yaml ]; then
    cp /app/config/dashboard.example.yaml /app/config/dashboard.yaml
fi

exec "$@"
