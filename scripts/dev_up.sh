#!/usr/bin/env bash
# Start Redis (if using local default), Celery worker, and FastAPI server.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
PORT="${PORT:-8000}"
REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-2}"
CELERY_POOL="${CELERY_POOL:-solo}" # solo avoids fork issues with mediapipe/ffmpeg on macOS

VENV="$ROOT_DIR/.venv"

if [[ -d "$VENV" ]]; then
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
else
  echo "Virtual environment not found at $VENV"
  echo "Create it with: uv venv .venv --python 3.11 && source .venv/bin/activate && uv pip install -r requirements.txt"
  exit 1
fi

start_redis=0

# Start local Redis only if using the default URL and nothing is listening.
if [[ "$REDIS_URL" == "redis://localhost:6379/0" ]]; then
  if ! nc -z localhost 6379 >/dev/null 2>&1; then
    if ! command -v redis-server >/dev/null 2>&1; then
      echo "redis-server not found. Install it (e.g., brew install redis) or point REDIS_URL to an existing instance."
      exit 1
    fi
    echo "Starting local Redis on port 6379..."
    redis-server --save "" --appendonly no --daemonize yes
    start_redis=1
  else
    echo "Redis already running on localhost:6379"
  fi
else
  echo "Using external Redis: $REDIS_URL"
fi

cleanup() {
  echo "Shutting down services..."
  if [[ -n "${CELERY_PID:-}" ]]; then
    kill "$CELERY_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${UVICORN_PID:-}" ]]; then
    kill "$UVICORN_PID" >/dev/null 2>&1 || true
  fi
  if [[ "$start_redis" -eq 1 ]]; then
    redis-cli shutdown >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

echo "Starting Celery worker (concurrency=$CELERY_CONCURRENCY)..."
celery -A src.celery_app.celery_app worker -l info --concurrency "$CELERY_CONCURRENCY" --pool "$CELERY_POOL" &
CELERY_PID=$!

echo "Starting FastAPI (uvicorn) on port $PORT..."
uvicorn src.main:app --host 0.0.0.0 --port "$PORT" &
UVICORN_PID=$!

echo "Services started."
echo "- API: http://localhost:$PORT"
echo "- Redis: $REDIS_URL"
echo "- Celery worker PID: $CELERY_PID"
echo "- Uvicorn PID: $UVICORN_PID"

wait
