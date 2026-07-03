#!/usr/bin/env zsh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"

status_line() {
  local name="$1"
  local state="$2"
  local detail="$3"
  printf "%-12s %-8s %s\n" "$name" "$state" "$detail"
}

cd "$ROOT_DIR"

printf "CrewPilot development status\n"
printf "----------------------------\n"

postgres_pid="$(lsof -tiTCP:5432 -sTCP:LISTEN 2>/dev/null | tr '\n' ' ' || true)"
if docker compose ps --status running postgres 2>/dev/null | grep -q "crewpilot-postgres"; then
  status_line "PostgreSQL" "RUNNING" "Docker container crewpilot-postgres"
elif [[ -n "$postgres_pid" ]]; then
  status_line "PostgreSQL" "RUNNING" "Port 5432 is listening (pid: ${postgres_pid})"
else
  status_line "PostgreSQL" "STOPPED" "Docker container is not running"
fi

api_pid="$(lsof -tiTCP:"$API_PORT" -sTCP:LISTEN 2>/dev/null | tr '\n' ' ' || true)"
if [[ -n "$api_pid" ]] && curl -fsS "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then
  status_line "API" "RUNNING" "http://localhost:${API_PORT} (pid: ${api_pid})"
elif [[ -n "$api_pid" ]]; then
  status_line "API" "RUNNING" "Port ${API_PORT} is listening (pid: ${api_pid}); HTTP check unavailable"
else
  status_line "API" "STOPPED" "Port ${API_PORT} is not listening"
fi

web_pid="$(lsof -tiTCP:"$WEB_PORT" -sTCP:LISTEN 2>/dev/null | tr '\n' ' ' || true)"
if [[ -n "$web_pid" ]] && curl -fsS "http://127.0.0.1:${WEB_PORT}" >/dev/null 2>&1; then
  status_line "Web" "RUNNING" "http://localhost:${WEB_PORT} (pid: ${web_pid})"
elif [[ -n "$web_pid" ]]; then
  status_line "Web" "RUNNING" "Port ${WEB_PORT} is listening (pid: ${web_pid}); HTTP check unavailable"
else
  status_line "Web" "STOPPED" "Port ${WEB_PORT} is not listening"
fi
