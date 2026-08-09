#!/usr/bin/env bash
# Run backend (FastAPI, hot reload) and frontend (Vite dev server) together.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$ROOT_DIR/backend/.env" ]; then
	echo "backend/.env not found — copying from backend/.env.example" >&2
	cp "$ROOT_DIR/backend/.env.example" "$ROOT_DIR/backend/.env"
fi

if [ ! -f "$ROOT_DIR/frontend/.env" ]; then
	echo "frontend/.env not found — copying from frontend/.env.example" >&2
	cp "$ROOT_DIR/frontend/.env.example" "$ROOT_DIR/frontend/.env"
fi

if [ ! -f "$ROOT_DIR/backend/config/dashboard.yaml" ]; then
	echo "backend/config/dashboard.yaml not found — copying from dashboard.example.yaml" >&2
	cp "$ROOT_DIR/backend/config/dashboard.example.yaml" "$ROOT_DIR/backend/config/dashboard.yaml"
fi

cleanup() {
	trap - EXIT INT TERM
	jobs -p | xargs -r kill 2>/dev/null
	wait 2>/dev/null
}
trap cleanup EXIT INT TERM

(cd "$ROOT_DIR/backend" && uv sync && uv run uvicorn app.main:app --reload --host localhost --port 8000) &

(cd "$ROOT_DIR/frontend" && npm install && npm run dev) &

wait
