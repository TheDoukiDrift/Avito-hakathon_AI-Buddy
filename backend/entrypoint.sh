#!/bin/sh
# Старт backend-контейнера: дождаться БД → миграции → сиды → uvicorn.
set -e

echo "[entrypoint] ждём PostgreSQL..."
python - <<'PY'
import os
import sys
import time

import psycopg

dsn = os.environ.get("DATABASE_URL", "")
# SQLAlchemy-URL вида postgresql+psycopg:// → psycopg принимает postgresql://
dsn = dsn.replace("postgresql+psycopg://", "postgresql://").replace(
    "postgresql+asyncpg://", "postgresql://"
)
if not dsn:
    print("[entrypoint] DATABASE_URL не задан", file=sys.stderr)
    sys.exit(1)

deadline = time.time() + 60
while True:
    try:
        with psycopg.connect(dsn, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        print("[entrypoint] PostgreSQL готов")
        break
    except Exception as exc:  # noqa: BLE001 — ждём любую ошибку соединения
        if time.time() > deadline:
            print(f"[entrypoint] PostgreSQL недоступен: {exc}", file=sys.stderr)
            sys.exit(1)
        time.sleep(2)
PY

echo "[entrypoint] применяем миграции..."
alembic upgrade head

echo "[entrypoint] загружаем сиды..."
python -m app.seeds

echo "[entrypoint] запускаем uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
