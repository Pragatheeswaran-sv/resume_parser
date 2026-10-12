#!/usr/bin/env bash
set -euo pipefail

# Single-container entrypoint that runs all three processes required by the
# Resume Tracker backend: the FastAPI API, the Celery worker, and the
# APScheduler-based email scheduler. Used for free single-instance hosting
# (e.g. Render) where separate always-on worker services are not available.

export PYTHONPATH="${PYTHONPATH:-/app}"
PORT="${PORT:-8000}"

pids=()

cleanup() {
    echo "[start.sh] Shutting down child processes..."
    for pid in "${pids[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
}
trap cleanup EXIT INT TERM

echo "[start.sh] Starting Celery worker..."
celery -A src.celery.celery_app.celery worker --loglevel=info --pool=solo &
pids+=("$!")

echo "[start.sh] Starting APScheduler..."
python scheduler_worker.py &
pids+=("$!")

echo "[start.sh] Starting API on port ${PORT}..."
exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT}"
