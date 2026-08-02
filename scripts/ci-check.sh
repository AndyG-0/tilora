#!/usr/bin/env bash
# Runs the same steps as the backend/frontend jobs in
# .github/workflows/ci.yml, so failures show up locally before a push. See
# CONTRIBUTING.md "Testing". (Does not build the docker-build job's images —
# that job only builds, it doesn't lint or test.)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() { printf 'ci-check.sh: %s\n' "$*" >&2; exit 1; }
info() { printf '\n==> %s\n' "$*"; }
require_command() { command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"; }

usage() {
	cat <<'EOF'
Usage: scripts/ci-check.sh

Runs the backend and frontend CI jobs locally, in the same order as
.github/workflows/ci.yml:

  backend:  uv sync, ruff check, ruff format --check, pytest
  frontend: npm ci, lint, format:check, check (svelte-check), test

Stops at the first failing step.
EOF
}

case "${1:-}" in
-h | --help)
	usage
	exit 0
	;;
"") ;;
*)
	usage
	fail "Unknown argument: $1"
	;;
esac

require_command uv
require_command npm

cd "$ROOT_DIR/backend"

info "Backend: uv sync"
uv sync

info "Backend: ruff check"
uv run ruff check .

info "Backend: ruff format --check"
uv run ruff format --check .

info "Backend: pytest"
uv run pytest

cd "$ROOT_DIR/frontend"

info "Frontend: npm ci"
npm ci

info "Frontend: lint"
npm run lint

info "Frontend: format:check"
npm run format:check

info "Frontend: check (svelte-check)"
npm run check

info "Frontend: test"
npm run test

info "All CI checks passed."
