#!/bin/sh
set -eu

wait_for_db() {
  python - <<'PY'
import os
import time
import psycopg

database_url = os.environ["DATABASE_URL"]
deadline = time.time() + int(os.environ.get("DB_WAIT_TIMEOUT", "90"))

last_error = None
while time.time() < deadline:
    try:
        with psycopg.connect(database_url):
            print("Database connection ready.")
            raise SystemExit(0)
    except Exception as exc:
        last_error = exc
        time.sleep(2)

raise SystemExit(f"Database did not become ready: {last_error}")
PY
}

mode="${1:-api}"

case "$mode" in
  api)
    wait_for_db
    alembic upgrade head
    python scripts/db/init_database.py
    exec uvicorn src.api.main:app --host 0.0.0.0 --port 8000
    ;;
  gui)
    wait_for_db
    exec python scripts/runtime/run_dashboard.py
    ;;
  worker)
    wait_for_db
    exec python scripts/run_continuous_pipeline.py
    ;;
  *)
    exec "$@"
    ;;
esac
