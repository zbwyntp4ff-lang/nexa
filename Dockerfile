# NEXA production image: FastAPI + Next.js behind Caddy (single public HTTPS port).
# Built remotely by Railway/Render — local Docker is not required.

FROM node:20-bookworm AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Same-origin API (Caddy proxies /api and /health to uvicorn).
ARG NEXT_PUBLIC_NEXA_PUBLIC_BETA=false
ENV NEXT_PUBLIC_NEXA_PUBLIC_BETA=${NEXT_PUBLIC_NEXA_PUBLIC_BETA}
ENV NEXT_PUBLIC_API_BASE_URL=
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=8080 \
    NEXA_API_PORT=8420 \
    NEXA_WEB_PORT=3000 \
    ENVIRONMENT=production \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl gnupg caddy procps \
      libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
      libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
      libgbm1 libasound2 libpango-1.0-0 libcairo2 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt \
    && playwright install chromium

COPY app ./app
COPY scripts/prod_start.sh ./scripts/prod_start.sh
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend-build /frontend/.next ./frontend/.next
COPY --from=frontend-build /frontend/public ./frontend/public
COPY --from=frontend-build /frontend/package.json ./frontend/package.json
COPY --from=frontend-build /frontend/package-lock.json ./frontend/package-lock.json
COPY --from=frontend-build /frontend/next.config.ts ./frontend/next.config.ts
COPY --from=frontend-build /frontend/node_modules ./frontend/node_modules

RUN chmod +x ./scripts/prod_start.sh \
    && mkdir -p /app/data /app/agent_workspace \
    && useradd --create-home --shell /bin/bash nexa \
    && chown -R nexa:nexa /app /ms-playwright

# Entrypoint starts as root only to chown the mounted volume, then drops to `nexa`
# for uvicorn/Next (see scripts/prod_start.sh). Do not expose secrets in the image.
USER root
EXPOSE 8080
# Shell form so ${PORT} expands (JSON/exec form does not run a shell).
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT:-8080}/health" || exit 1

CMD ["./scripts/prod_start.sh"]
