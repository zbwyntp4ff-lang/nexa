#!/usr/bin/env bash
set -euo pipefail

API_PORT="${NEXA_API_PORT:-8420}"
WEB_PORT="${NEXA_WEB_PORT:-3000}"
PORT="${PORT:-8080}"

mkdir -p /app/data /app/agent_workspace

echo "[nexa] starting API on :${API_PORT}"
python -m uvicorn app.main:app --host 127.0.0.1 --port "${API_PORT}" --proxy-headers --forwarded-allow-ips='*' &
API_PID=$!

echo "[nexa] starting Next.js on :${WEB_PORT}"
(
  cd /app/frontend
  npx next start -H 127.0.0.1 -p "${WEB_PORT}"
) &
WEB_PID=$!

cleanup() {
  kill "${API_PID}" "${WEB_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Wait for API before exposing Caddy
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "[nexa] starting Caddy on :${PORT}"
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
