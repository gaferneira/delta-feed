#!/usr/bin/env bash
# Start the whole local stack: backend API, background worker and frontend.
#
# Dev-only (SQLite, DEBUG on). Output of each process is prefixed with its name;
# Ctrl-C stops all three. This script never runs migrations: if some are pending
# it prints the command to run, because applying them silently would change your DB.
#
# Usage: ./scripts/dev.sh        (run ./scripts/init.sh once beforehand)

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Load local settings from .env (gitignored; see .env.example). Plain KEY=value lines
# only, nothing is executed; a variable already set in your shell wins.
if [ -f "$ROOT_DIR/.env" ]; then
  while IFS='=' read -r key value || [ -n "$key" ]; do
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    value="${value%$'\r'}"
    value="${value%\"}"; value="${value#\"}"
    [ -z "${!key+x}" ] && export "$key=$value"
  done < "$ROOT_DIR/.env"
fi

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-4321}"
export DJANGO_DEBUG="${DJANGO_DEBUG:-true}"

for tool in uv npm; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "error: $tool is not installed." >&2
    exit 1
  fi
done

if ! (cd "$ROOT_DIR/backend" && uv run python manage.py migrate --check >/dev/null 2>&1); then
  echo "note: database migrations are pending or the database is not set up." >&2
  echo "      Apply them yourself, then restart:  cd backend && uv run python manage.py migrate" >&2
fi

PIDS=()

cleanup() {
  trap - INT TERM EXIT
  echo
  echo "Stopping backend, worker and frontend..."
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null
  done
  wait 2>/dev/null
}
trap cleanup INT TERM EXIT

# start <label> <directory> <command...>: run in the background, prefix every output line.
start() {
  local label="$1" dir="$2"
  shift 2
  (
    cd "$dir" || exit 1
    # exec so the PID we kill is the real process, not a wrapper shell.
    exec "$@" 2>&1
  ) > >(sed -u "s/^/[$label] /") &
  PIDS+=("$!")
}

start backend  "$ROOT_DIR/backend"  uv run python manage.py runserver "$BACKEND_PORT"
start worker   "$ROOT_DIR/backend"  uv run python manage.py run_worker
start frontend "$ROOT_DIR/frontend" env BACKEND_URL="http://localhost:$BACKEND_PORT" npm run dev -- --port "$FRONTEND_PORT"

echo "Delta Feed dev stack: http://localhost:$FRONTEND_PORT  (Ctrl-C stops everything)"
wait
