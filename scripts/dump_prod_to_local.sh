#!/usr/bin/env bash
# Dump production PostgreSQL database and restore into local SQLite.
#
# Connects Django directly to prod DB, runs dumpdata, then loaddata into local SQLite.
# No local PostgreSQL needed.
#
# Prerequisites:
#   - Python virtualenv activated
#   - Production DB credentials in .env (PROD_DB_*)
#
# Usage:
#   bash scripts/dump_prod_to_local.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ── Load .env ────────────────────────────────────────────────────
if [[ -f "$PROJECT_DIR/.env" ]]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

# ── Build prod DATABASE_URL ──────────────────────────────────────
PROD_HOST="${PROD_DB_HOST:?Set PROD_DB_HOST in .env}"
PROD_PORT="${PROD_DB_PORT:-5432}"
PROD_DB="${PROD_DB_NAME:?Set PROD_DB_NAME in .env}"
PROD_USER="${PROD_DB_USER:?Set PROD_DB_USER in .env}"
PROD_PASSWORD="${PROD_DB_PASSWORD:?Set PROD_DB_PASSWORD in .env}"

PROD_DATABASE_URL="postgres://${PROD_USER}:${PROD_PASSWORD}@${PROD_HOST}:${PROD_PORT}/${PROD_DB}"

LOCAL_DB="$PROJECT_DIR/db.sqlite3"
DUMP_FILE="$PROJECT_DIR/prod_dump.json"

# ── Step 1: Dumpdata from prod ───────────────────────────────────
echo "==> Connecting to production and exporting data..."
DATABASE_URL="$PROD_DATABASE_URL" \
ENV="prod" \
    python "$PROJECT_DIR/manage.py" dumpdata \
    --natural-foreign \
    --natural-primary \
    --exclude contenttypes \
    --exclude auth.permission \
    --exclude sessions \
    --indent 2 \
    -o "$DUMP_FILE"

DUMP_SIZE=$(du -h "$DUMP_FILE" | cut -f1)
echo "==> Export complete (${DUMP_SIZE})"

# ── Step 2: Backup and replace local DB ──────────────────────────
echo "==> Backing up local database..."
if [[ -f "$LOCAL_DB" ]]; then
    cp "$LOCAL_DB" "${LOCAL_DB}.backup"
    echo "    Saved to db.sqlite3.backup"
fi

echo "==> Removing old local database..."
rm -f "$LOCAL_DB"

echo "==> Running migrations on fresh SQLite..."
ENV="" python "$PROJECT_DIR/manage.py" migrate --run-syncdb

echo "==> Loading production data into local SQLite..."
ENV="" python "$PROJECT_DIR/manage.py" loaddata "$DUMP_FILE"

# ── Cleanup ──────────────────────────────────────────────────────
echo "==> Cleaning up..."
rm -f "$DUMP_FILE"

echo ""
echo "==> Done! Local database restored from production."