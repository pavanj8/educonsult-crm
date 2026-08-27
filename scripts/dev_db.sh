#!/usr/bin/env bash
# Build a local development database at the current migration head and load the
# demo catalog into it.
#
# This exists because there was no repeatable path to a working local database.
# The previously checked-in backend/dev.db had no alembic_version row at all --
# it had been produced by a one-off create_all() and then drifted away from the
# schema, so every analytics query failed against it. Anything hand-built has
# the same fate; this script is the thing to re-run instead.
#
# Usage:
#   scripts/dev_db.sh                 # build backend/dev.db (recreates it)
#   DATABASE_URL=... scripts/dev_db.sh  # build some other database instead
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BE_DIR="${HARNESS_BACKEND_DIR:-backend}"
cd "$ROOT/$BE_DIR"

# Prefer the local venv when there is one, matching scripts/check.sh.
if [ -d "venv/bin" ]; then
  PATH="$PWD/venv/bin:$PATH"; export PATH
fi

DB_URL="${DATABASE_URL:-sqlite:///./dev.db}"
export DATABASE_URL="$DB_URL"

# For the default file-backed sqlite case, start clean: the seed inserts fixed
# primary keys, so re-running against existing rows would collide.
if [ "$DB_URL" = "sqlite:///./dev.db" ] && [ -f dev.db ]; then
  echo "== moving aside existing dev.db =="
  mv -f dev.db "dev.db.bak"
fi

echo "== migrating to head: $DB_URL =="
python -m alembic upgrade head

echo "== seeding demo data =="
python -m app.seed

echo
echo "Local database ready."
echo "Sign in with any seeded account; the demo password is printed above."
