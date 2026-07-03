#!/bin/sh
set -eu

python -m alembic upgrade head
python -m app.db.bootstrap_auth

if [ "${RUN_SEED_DATA:-true}" = "true" ]; then
  python -m app.db.seed
fi

exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
