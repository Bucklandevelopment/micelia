#!/bin/bash
# =============================================================================
# Micelia: Entrypoint Script
# =============================================================================
# Waits for PostgreSQL, runs migrations if available, then starts uvicorn.
# =============================================================================

set -e

echo "============================================="
echo "  Micelia: Starting up..."
echo "============================================="

# ---------------------------------------------------------------------------
# 1. Wait for PostgreSQL to be ready
# ---------------------------------------------------------------------------
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-idm}"

echo "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."

MAX_RETRIES=30
RETRY_COUNT=0

while ! pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -q; do
  RETRY_COUNT=$((RETRY_COUNT + 1))
  if [ "${RETRY_COUNT}" -ge "${MAX_RETRIES}" ]; then
    echo "ERROR: PostgreSQL not ready after ${MAX_RETRIES} attempts. Exiting."
    exit 1
  fi
  echo "  PostgreSQL not ready yet (attempt ${RETRY_COUNT}/${MAX_RETRIES})..."
  sleep 2
done

echo "PostgreSQL is ready!"

# ---------------------------------------------------------------------------
# 2. Run database migrations
# ---------------------------------------------------------------------------
if [ -f "alembic.ini" ]; then
  echo "Running Alembic database migrations..."
  alembic upgrade head
  echo "Migrations complete."
else
  echo "No alembic.ini found. Tables will be created by SQLAlchemy on startup."
fi

# ---------------------------------------------------------------------------
# 3. Start the application
# ---------------------------------------------------------------------------
GATEWAY_HOST="${GATEWAY_HOST:-0.0.0.0}"
GATEWAY_PORT="${GATEWAY_PORT:-8888}"

echo "Starting Micelia on ${GATEWAY_HOST}:${GATEWAY_PORT}..."
echo "============================================="

# uvicorn requires lowercase log-level
LOG_LEVEL_LOWER=$(echo "${LOG_LEVEL:-info}" | tr '[:upper:]' '[:lower:]')

exec uvicorn app.main:app \
  --host "${GATEWAY_HOST}" \
  --port "${GATEWAY_PORT}" \
  --log-level "${LOG_LEVEL_LOWER}"
