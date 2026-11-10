#!/bin/sh
# Container entrypoint: wait for the DB, migrate, seed (idempotent), then run CMD.
set -eu

if [ "${SKIP_MIGRATIONS:-0}" != "1" ]; then
  attempts="${DB_WAIT_ATTEMPTS:-30}"
  i=0
  until alembic upgrade head; do
    i=$((i + 1))
    if [ "$i" -ge "$attempts" ]; then
      echo "[entrypoint] alembic upgrade failed after ${attempts} attempts" >&2
      exit 1
    fi
    echo "[entrypoint] database not ready (attempt ${i}/${attempts}), retrying in 2s"
    sleep 2
  done

  python -m app.seeds
fi

exec "$@"
