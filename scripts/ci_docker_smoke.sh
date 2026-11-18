#!/usr/bin/env bash
# Build + smoke-test the production Docker image locally or in CI.
# Does NOT push to a registry, create cloud resources, or public-deploy.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not available on this machine." >&2
  echo "Run this script on a host with Docker, or use GitHub Actions workflow docker-image.yml." >&2
  exit 127
fi

IMAGE_TAG="${NEXA_CI_IMAGE_TAG:-nexa-ci:local}"
CONTAINER_NAME="${NEXA_CI_CONTAINER_NAME:-nexa-ci-smoke}"
HOST_PORT="${NEXA_CI_HOST_PORT:-18080}"
# Non-default PORT proves Caddy uses \$PORT (not a hard-coded 8080-only listen).
CONTAINER_PORT="${NEXA_CI_CONTAINER_PORT:-18080}"

# Safe production-like env — no real secrets, no AI_PROVIDER=mock.
# Placeholder key is intentionally fake; chat quality is out of scope for smoke.
PUBLIC_ORIGIN="https://ci-nexa.example"

ENV_ARGS=(
  -e "PORT=${CONTAINER_PORT}"
  -e "NEXA_PUBLIC_BETA=true"
  -e "ENVIRONMENT=production"
  -e "NEXA_STORAGE_MODE=persistent"
  -e "TOKENS_ENFORCE=true"
  -e "AUTH_SINGLE_USER=false"
  -e "AUTH_SKIP_EMAIL_VERIFICATION=false"
  -e "AUTH_COOKIE_SECURE=true"
  -e "AUTH_BOOTSTRAP_FIRST_OWNER=false"
  -e "EMAIL_PROVIDER=smtp"
  -e "SMTP_HOST=smtp.ci.invalid"
  -e "SMTP_PORT=587"
  -e "EMAIL_FROM=noreply@ci-nexa.example"
  -e "SMTP_USE_TLS=true"
  -e "AI_PROVIDER=openrouter"
  -e "OPENROUTER_MODEL=openai/gpt-4o-mini"
  -e "OPENROUTER_API_KEY=ci-placeholder-not-a-real-key"
  -e "ALLOW_MODEL_FALLBACK=false"
  -e "NEXA_AI_KILL_SWITCH=false"
  -e "MEMORY_BACKEND=sql"
  -e "DATABASE_URL=sqlite:///data/nexa-ci.db"
  -e "WORKFLOWS_ENABLED=false"
  -e "AUTH_PUBLIC_BASE_URL=${PUBLIC_ORIGIN}"
  -e "CORS_ALLOWED_ORIGINS=${PUBLIC_ORIGIN}"
  -e "BILLING_PUBLIC_BASE_URL=${PUBLIC_ORIGIN}"
  -e "AGENT_MAX_PARALLEL_PER_USER=2"
  -e "API_RATE_LIMIT_PER_MINUTE=60"
  -e "IMAGE_PROVIDER=none"
  -e "VIDEO_PROVIDER=none"
  -e "WEB_SEARCH_PROVIDER=duckduckgo"
  -e "LOG_LEVEL=INFO"
)

echo "==> docker build ${IMAGE_TAG}"
docker build -t "${IMAGE_TAG}" .

cleanup_container() {
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
}
trap cleanup_container EXIT

cleanup_container

start_container() {
  docker run -d \
    --name "${CONTAINER_NAME}" \
    -p "${HOST_PORT}:${CONTAINER_PORT}" \
    "${ENV_ARGS[@]}" \
    "${IMAGE_TAG}"
}

wait_health() {
  local attempts="${1:-120}"
  local ok=0
  for _ in $(seq 1 "${attempts}"); do
    if curl -fsS "http://127.0.0.1:${HOST_PORT}/health" >/tmp/nexa_ci_health.json 2>/dev/null; then
      ok=1
      break
    fi
    if ! docker ps --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
      echo "Container exited early. Logs:" >&2
      docker logs "${CONTAINER_NAME}" >&2 || true
      return 1
    fi
    sleep 2
  done
  if [ "${ok}" != "1" ]; then
    echo "Health check timed out. Logs:" >&2
    docker logs "${CONTAINER_NAME}" >&2 || true
    return 1
  fi
  return 0
}

echo "==> docker run (PORT=${CONTAINER_PORT} → host ${HOST_PORT})"
start_container

echo "==> wait for /health on host :${HOST_PORT}"
wait_health 120

echo "==> health body:"
cat /tmp/nexa_ci_health.json
echo

python3 - <<'PY'
import json, sys
data = json.load(open("/tmp/nexa_ci_health.json", encoding="utf-8"))
status = (data.get("status") or "").lower()
if status not in {"ok", "degraded"}:
    print("unexpected health status:", data, file=sys.stderr)
    sys.exit(1)
if data.get("storage_mode") != "persistent":
    print("expected storage_mode=persistent, got:", data.get("storage_mode"), file=sys.stderr)
    sys.exit(1)
if (data.get("ai_provider") or "").lower() == "mock":
    print("ai_provider must not be mock under production smoke", file=sys.stderr)
    sys.exit(1)
if data.get("database_ok") is False:
    print("database_ok is false:", data, file=sys.stderr)
    sys.exit(1)
print("health_assertions=ok")
PY

echo "==> assert Caddy listened on PORT=${CONTAINER_PORT} (from logs)"
# Caddy starts asynchronously after the API health endpoint becomes ready.
# Poll briefly to avoid a log-ordering race in fast CI containers.
caddy_started=0
for _ in $(seq 1 15); do
  if docker logs "${CONTAINER_NAME}" 2>&1 | grep -Fq "starting Caddy on :${CONTAINER_PORT}"; then
    caddy_started=1
    break
  fi
  sleep 1
done
if [ "${caddy_started}" != "1" ]; then
  echo "Did not find Caddy start line for PORT=${CONTAINER_PORT}. Logs:" >&2
  docker logs "${CONTAINER_NAME}" >&2 || true
  exit 1
fi

echo "==> process check (caddy / uvicorn / next)"
docker exec "${CONTAINER_NAME}" bash -lc '
  set -euo pipefail
  ps -eo pid,ppid,cmd --no-headers | head -n 50
  pgrep -af caddy >/dev/null
  pgrep -af "uvicorn app.main:app" >/dev/null
  pgrep -af "next" >/dev/null
  echo "process_assertions=ok"
'

echo "==> UI via Caddy (Next.js)"
ui_code="$(curl -sS -o /tmp/nexa_ci_ui.html -w "%{http_code}" "http://127.0.0.1:${HOST_PORT}/" || true)"
if [ "${ui_code}" != "200" ]; then
  echo "UI HTTP ${ui_code} (expected 200). Body head:" >&2
  head -c 400 /tmp/nexa_ci_ui.html >&2 || true
  echo >&2
  exit 1
fi
# Next HTML or a document shell — reject empty / obvious API JSON errors.
if ! head -c 200 /tmp/nexa_ci_ui.html | grep -qiE '<(!doctype )?html|nexa|__next'; then
  echo "UI body does not look like Next HTML:" >&2
  head -c 400 /tmp/nexa_ci_ui.html >&2 || true
  echo >&2
  exit 1
fi
echo "ui_assertions=ok (HTTP ${ui_code})"

echo "==> SIGTERM via kill -TERM 1 (entrypoint / prod_start.sh)"
docker exec "${CONTAINER_NAME}" bash -lc 'kill -TERM 1'

stopped=0
for _ in $(seq 1 45); do
  running="$(docker inspect -f '{{.State.Running}}' "${CONTAINER_NAME}" 2>/dev/null || echo false)"
  if [ "${running}" = "false" ]; then
    stopped=1
    break
  fi
  sleep 1
done

if [ "${stopped}" != "1" ]; then
  echo "Container did not stop after SIGTERM; forcing docker stop" >&2
  docker stop -t 5 "${CONTAINER_NAME}" >/dev/null || true
  exit 1
fi

exit_code="$(docker inspect -f '{{.State.ExitCode}}' "${CONTAINER_NAME}")"
echo "container_exit_code=${exit_code}"

echo "==> leftover check: container must not be running; exec must fail"
if docker ps --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
  echo "container still running after SIGTERM" >&2
  exit 1
fi
if docker exec "${CONTAINER_NAME}" true 2>/dev/null; then
  echo "docker exec unexpectedly succeeded after stop (processes may still be live)" >&2
  exit 1
fi
echo "leftover_assertions=ok"

# Re-run briefly and confirm docker stop also cleans up (platform path).
echo "==> second boot: docker stop cleanup path"
docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
start_container >/dev/null
wait_health 90

echo "==> processes before docker stop"
docker exec "${CONTAINER_NAME}" bash -lc 'pgrep -af "caddy|uvicorn|next" || true'

docker stop -t 25 "${CONTAINER_NAME}" >/dev/null
running="$(docker inspect -f '{{.State.Running}}' "${CONTAINER_NAME}")"
if [ "${running}" != "false" ]; then
  echo "docker stop left container running" >&2
  exit 1
fi
if docker exec "${CONTAINER_NAME}" true 2>/dev/null; then
  echo "docker exec succeeded after docker stop" >&2
  exit 1
fi

echo "==> SMOKE PASS (image=${IMAGE_TAG}, PORT=${CONTAINER_PORT})"
