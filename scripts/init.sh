#!/usr/bin/env bash
# Local development bootstrap for Delta Feed.
#
# Scope: dev-only setup (SQLite backend DB, no Postgres/pgvector, no HTTPS,
# no Compose). This is NOT a production install script — Milestone 6
# (private deployment) has not been implemented or verified yet. See
# README.md#project-status before treating this as a deploy story.
#
# What this does:
#   - backend: uv sync (creates/updates the venv from uv.lock) + migrate
#   - backend: prompts for the first user if none exists (interactive only)
#   - frontend: npm install
#
# Usage: ./scripts/init.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Dev-only: DEBUG on permits the built-in insecure dev SECRET_KEY and non-Secure
# cookies. Any real deployment must set DJANGO_SECRET_KEY instead (settings fail fast).
export DJANGO_DEBUG="${DJANGO_DEBUG:-true}"

echo "==> Backend: uv sync"
cd "$ROOT_DIR/backend"
if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv is not installed. Install it first: https://docs.astral.sh/uv/" >&2
  exit 1
fi
uv sync

echo "==> Backend: django migrate (SQLite dev DB)"
uv run python manage.py migrate

echo "==> Backend: django check"
uv run python manage.py check

# The reader has no sign-up; without a user the login screen is a dead end.
echo "==> Backend: initial user"
if uv run python manage.py shell -v 0 -c \
  "import sys; from django.contrib.auth import get_user_model; sys.exit(0 if get_user_model().objects.exists() else 1)"; then
  echo "A user already exists; skipping."
elif [ -t 0 ]; then
  echo "No user yet. Create the account you will sign in with:"
  uv run python manage.py createsuperuser
else
  echo "No user yet and no terminal to prompt. Create one later with:"
  echo "  cd backend && uv run python manage.py createsuperuser"
  echo "or open /setup in the reader with a token from the backend logs or:"
  echo "  cd backend && uv run python manage.py setup_token"
fi

echo "==> Frontend: npm install"
cd "$ROOT_DIR/frontend"
if ! command -v npm >/dev/null 2>&1; then
  echo "error: npm is not installed." >&2
  exit 1
fi
npm install

cat <<'EOF'

==> Done.

Run the backend dev server:
  cd backend && DJANGO_DEBUG=true uv run python manage.py runserver 8000

Run the frontend dev server (in another shell):
  cd frontend && BACKEND_URL=http://localhost:8000 npm run dev

Run the test suites:
  cd backend && uv run pytest -q
  cd frontend && npm test

This is a dev-only bootstrap. No secrets, no production database, no
HTTPS/ingress configuration is set up by this script.
EOF
