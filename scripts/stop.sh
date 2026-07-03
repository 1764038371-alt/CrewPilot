#!/usr/bin/env zsh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"
STOP_REQUEST_FILE="${TMPDIR:-/tmp}/crewpilot-dev-stop"

touch "$STOP_REQUEST_FILE"

stop_port() {
  local port="$1"
  local name="$2"
  local pids
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | tr '\n' ' ' || true)"
  if [[ -z "$pids" ]]; then
    printf "[STOP] %s is not running on port %s.\n" "$name" "$port"
    return
  fi
  printf "[STOP] Stopping %s on port %s (pid: %s)...\n" "$name" "$port" "$pids"
  kill $=pids 2>/dev/null || true
  for _ in {1..20}; do
    sleep 0.2
    pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | tr '\n' ' ' || true)"
    if [[ -z "$pids" ]]; then
      return
    fi
  done
  printf "[STOP] %s did not stop cleanly; forcing stop (pid: %s)...\n" "$name" "$pids"
  kill -9 $=pids 2>/dev/null || true
}

stop_port "$API_PORT" "API"
stop_port "$WEB_PORT" "Web"

cd "$ROOT_DIR"
printf "[STOP] Stopping Docker Compose services...\n"
docker compose stop
printf "[STOP] Done.\n"
