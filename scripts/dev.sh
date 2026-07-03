#!/usr/bin/env zsh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"
STOP_REQUEST_FILE="${TMPDIR:-/tmp}/crewpilot-dev-stop"

API_COLOR=$'\033[36m'
WEB_COLOR=$'\033[35m'
SYS_COLOR=$'\033[33m'
ERR_COLOR=$'\033[31m'
RESET=$'\033[0m'

log_system() {
  printf "%s[DEV]%s %s\n" "$SYS_COLOR" "$RESET" "$1"
}

fail_if_port_busy() {
  local port="$1"
  local name="$2"
  local pid
  pid="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | tr '\n' ' ' || true)"
  if [[ -n "$pid" ]]; then
    printf "%s[DEV]%s %s is already listening on port %s (pid: %s).\n" "$ERR_COLOR" "$RESET" "$name" "$port" "$pid"
    printf "%s[DEV]%s Run 'make stop' first, then retry 'make dev'.\n" "$ERR_COLOR" "$RESET"
    exit 1
  fi
}

prefix_api() {
  awk -v prefix="${API_COLOR}[API]${RESET} " '{ print prefix $0; fflush(); }'
}

prefix_web() {
  awk -v prefix="${WEB_COLOR}[WEB]${RESET} " '{ print prefix $0; fflush(); }'
}

cleanup() {
  local exit_code="$?"
  trap - INT TERM EXIT
  if [[ -n "${API_PID:-}" ]] && kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" 2>/dev/null || true
  fi
  if [[ -n "${WEB_PID:-}" ]] && kill -0 "$WEB_PID" 2>/dev/null; then
    kill "$WEB_PID" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
  if [[ "$exit_code" -ne 0 ]]; then
    printf "%s[DEV]%s Development environment stopped because one process exited with an error.\n" "$ERR_COLOR" "$RESET"
  else
    log_system "Development environment stopped."
  fi
  exit "$exit_code"
}

trap cleanup INT TERM EXIT

cd "$ROOT_DIR"
rm -f "$STOP_REQUEST_FILE"

fail_if_port_busy "$API_PORT" "API"
fail_if_port_busy "$WEB_PORT" "Web"

log_system "Clearing Web development cache..."
rm -rf "$ROOT_DIR/apps/web/.next"

log_system "Starting PostgreSQL with Docker Compose..."
docker compose up -d postgres

log_system "Starting API on http://localhost:${API_PORT}"
(
  cd "$ROOT_DIR/apps/api"
  .venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port "$API_PORT" 2>&1 | prefix_api
) &
API_PID="$!"

log_system "Starting Web on http://localhost:${WEB_PORT}"
(
  cd "$ROOT_DIR/apps/web"
  pnpm exec next dev --hostname 0.0.0.0 --port "$WEB_PORT" 2>&1 | prefix_web
) &
WEB_PID="$!"

log_system "Ready. Open http://localhost:${WEB_PORT}"
log_system "Press Ctrl+C to stop API/Web. Run 'make stop' to stop Docker too."

while true; do
  if ! kill -0 "$API_PID" 2>/dev/null; then
    if [[ -f "$STOP_REQUEST_FILE" ]]; then
      exit 0
    fi
    printf "%s[DEV]%s API process exited. Stopping Web...\n" "$ERR_COLOR" "$RESET"
    exit 1
  fi
  if ! kill -0 "$WEB_PID" 2>/dev/null; then
    if [[ -f "$STOP_REQUEST_FILE" ]]; then
      exit 0
    fi
    printf "%s[DEV]%s Web process exited. Stopping API...\n" "$ERR_COLOR" "$RESET"
    exit 1
  fi
  sleep 1
done
