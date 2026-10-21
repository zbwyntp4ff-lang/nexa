#!/usr/bin/env bash
# Single-container entrypoint: uvicorn + Next.js + Caddy on $PORT.
# Do not exec over the shell before children are registered — SIGTERM must
# reach API/Web so FastAPI lifespan cleanup can run.
set -euo pipefail

API_PORT="${NEXA_API_PORT:-8420}"
WEB_PORT="${NEXA_WEB_PORT:-3000}"
PORT="${PORT:-8080}"

# Railway/Render volumes often mount as root; the app runs as user `nexa`.
mkdir -p \
  /app/data \
  /app/data/attachments_tmp \
  /app/data/plugin_workspaces \
  /app/data/videos \
  /app/data/oauth \
  /app/data/legal \
  /app/agent_workspace

if [ "$(id -u)" = "0" ]; then
  chown -R nexa:nexa /app/data /app/agent_workspace || true
  run_app() { runuser -u nexa -- "$@"; }
else
  run_app() { "$@"; }
fi

API_PID=""
WEB_PID=""
CADDY_PID=""

_stop_pid() {
  local pid="${1:-}"
  [ -n "${pid}" ] || return 0
  if kill -0 "${pid}" 2>/dev/null; then
    kill -TERM "${pid}" 2>/dev/null || true
  fi
}

cleanup() {
  # Idempotent — EXIT runs after INT/TERM as well.
  if [ "${NEXA_CLEANING:-0}" = "1" ]; then
    return 0
  fi
  NEXA_CLEANING=1
  echo "[nexa] shutting down (SIGTERM/INT)…"
  _stop_pid "${CADDY_PID}"
  _stop_pid "${API_PID}"
  _stop_pid "${WEB_PID}"
  # Fallbacks: npx/runuser may leave grandchildren if only the wrapper PID was hit.
  pkill -TERM -f "uvicorn app.main:app" 2>/dev/null || true
  pkill -TERM -f "next-server" 2>/dev/null || true
  pkill -TERM -f "next start" 2>/dev/null || true
  pkill -TERM -f "caddy run" 2>/dev/null || true
  # Brief grace, then force-kill leftovers in this container only.
  sleep 2
  pkill -KILL -f "uvicorn app.main:app" 2>/dev/null || true
  pkill -KILL -f "next-server" 2>/dev/null || true
  pkill -KILL -f "next start" 2>/dev/null || true
  pkill -KILL -f "caddy run" 2>/dev/null || true
  wait || true
}
trap cleanup EXIT INT TERM

echo "[nexa] starting API on :${API_PORT}"
run_app python -m uvicorn app.main:app --host 127.0.0.1 --port "${API_PORT}" --proxy-headers --forwarded-allow-ips='*' &
API_PID=$!

echo "[nexa] starting Next.js on :${WEB_PORT}"
# Avoid an extra subshell so WEB_PID tracks the direct child of this script.
cd /app/frontend
run_app npx next start -H 127.0.0.1 -p "${WEB_PORT}" &
WEB_PID=$!
cd /app

# Wait for API before exposing Caddy (platform health checks hit $PORT).
for _ in $(seq 1 90); do
  if curl -fsS "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  # Fail fast if API crashed during boot (e.g. ProductionConfigError).
  if ! kill -0 "${API_PID}" 2>/dev/null; then
    echo "[nexa] API process exited before becoming healthy" >&2
    exit 1
  fi
  sleep 1
done

if ! curl -fsS "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then
  echo "[nexa] API health check timed out on :${API_PORT}" >&2
  exit 1
fi

echo "[nexa] starting Caddy on :${PORT}"
# Keep Caddy in the background so this shell retains the signal trap.
# (Previously `exec caddy` replaced the shell and orphaned uvicorn/Next.)
caddy run --config /etc/caddy/Caddyfile --adapter caddyfile &
CADDY_PID=$!

# Block until Caddy exits; trap handles the rest.
wait "${CADDY_PID}"
exit_code=$?
# If Caddy exited on its own, still run cleanup for siblings via EXIT trap.
exit "${exit_code}"
