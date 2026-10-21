# NEXA — Remote Docker Image Validation

Validate the **production Dockerfile** (Caddy + FastAPI + Next.js) without
publishing the app, pushing an image to a registry, or creating cloud resources.

## What runs

| Piece | Path |
|-------|------|
| Workflow | [`.github/workflows/docker-image.yml`](../.github/workflows/docker-image.yml) |
| Smoke script | [`scripts/ci_docker_smoke.sh`](../scripts/ci_docker_smoke.sh) |
| Image | root [`Dockerfile`](../Dockerfile) + [`scripts/prod_start.sh`](../scripts/prod_start.sh) |
| Staging env reference | [`deploy/render-staging.example.yaml`](../deploy/render-staging.example.yaml) |

Smoke env matches public-beta guards: `NEXA_PUBLIC_BETA=true`, `TOKENS_ENFORCE=true`,
email verification on, `EMAIL_PROVIDER=smtp` (host set, no real mail),
`AI_PROVIDER=openrouter` + named model (**not** `mock`, **not** `openrouter/free`),
placeholder API key only.

Checks:

1. `docker build` from the current Dockerfile  
2. Container listens on non-default `PORT` (18080) via Caddy  
3. `GET /health` → ok/degraded, `storage_mode=persistent`, `ai_provider≠mock`  
4. Processes: caddy, uvicorn, next  
5. `GET /` through Caddy returns Next HTML  
6. `SIGTERM` to PID 1 stops the container; `docker exec` fails afterward  
7. Second boot + `docker stop` also leaves no running container  

No `docker login` / `docker push`.

## How to run on GitHub Actions

**Prerequisites (manual / repo setup):**

1. Push this repository to GitHub (this prep machine may have **no git remote**).  
2. Enable **Actions** for the repository.  
3. Ensure `.github/workflows/docker-image.yml` is on the branch you run.  

**Trigger:**

- **Actions → “Docker image validation” → Run workflow** (`workflow_dispatch`), or  
- Push / open a PR that touches Dockerfile, `prod_start.sh`, frontend, `app/**`, etc. (see path filters in the workflow).

**Do not claim success** until the Actions run is green. Download the failure artifact `nexa-docker-smoke-logs-*` if it fails.

## How to run locally (Docker required)

```bash
chmod +x scripts/prod_start.sh scripts/ci_docker_smoke.sh
./scripts/ci_docker_smoke.sh
```

Optional overrides:

```bash
export NEXA_CI_IMAGE_TAG=nexa-ci:local
export NEXA_CI_HOST_PORT=18080
export NEXA_CI_CONTAINER_PORT=18080
./scripts/ci_docker_smoke.sh
```

## Status on the preparation workstation

Recorded facts (do not invent a pass):

| Check | Result |
|-------|--------|
| Dockerfile / `.dockerignore` / `prod_start.sh` / staging yaml | Reviewed |
| Workflow + smoke script present | Yes |
| Local Docker CLI | **Not installed** — build/smoke **not executed** here |
| `gh` CLI / git remote | **Missing / no remote** — Actions run **not triggered** from here |
| Unit/guard tests (non-Docker) | See session report (`pytest` open-beta / guards) |

Until a GitHub Actions run (or a local Docker smoke) completes, **Docker image validation = NOT YET VERIFIED**.
