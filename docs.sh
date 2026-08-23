#!/usr/bin/env bash
# Run the documentation site locally with live reload for testing.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8080}"

# Detect primary LAN IP on macOS / Linux if listening on all interfaces
if [ "$HOST" = "0.0.0.0" ]; then
	LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")"
else
	LAN_IP="$HOST"
fi

echo ""
echo "============================================================"
echo " Tilora Documentation Server Starting"
echo " Local URL: http://localhost:${PORT}"
if [ "$HOST" = "0.0.0.0" ]; then
	echo " LAN URL:   http://${LAN_IP}:${PORT}"
fi
echo "============================================================"
echo ""

(cd "$ROOT_DIR/backend" && uv sync --only-group docs --quiet)

exec uv run --project "$ROOT_DIR/backend" mkdocs serve -f "$ROOT_DIR/mkdocs.yml" --dev-addr "${HOST}:${PORT}" "$@"
