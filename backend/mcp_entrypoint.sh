#!/bin/sh
# Entrypoint for the MCP tools server (separate compose service).
# It only waits for the database and then runs CMD: migrations and seeds belong
# to the backend service alone — running them here would race the backend
# against an empty database on the very first `docker compose up`.
set -eu

check_db() {
  python -c '
import sys

from app.config import get_settings

dsn = get_settings().database_url
if dsn.startswith("sqlite"):
    sys.exit(0)

import psycopg

psycopg.connect(dsn.replace("+psycopg", ""), connect_timeout=3).close()
'
}

attempts="${DB_WAIT_ATTEMPTS:-30}"
i=0
until check_db; do
  i=$((i + 1))
  if [ "$i" -ge "$attempts" ]; then
    echo "[mcp-entrypoint] database not reachable after ${attempts} attempts" >&2
    exit 1
  fi
  echo "[mcp-entrypoint] database not ready (attempt ${i}/${attempts}), retrying in 2s"
  sleep 2
done

exec "$@"
