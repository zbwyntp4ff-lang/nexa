# NEXA storage matrix (public durable launch)

| Component | Backend | Path / env | Survives restart? | Needs volume? |
|-----------|---------|------------|-------------------|---------------|
| Auth users / sessions / codes | JSON file | `AUTH_STORE_PATH` → `data/auth_store.json` | Yes if volume | **Yes** |
| Conversations (server sync) | SQL | `DATABASE_URL` (`conversations` table) | Yes | **Yes** (SQLite file on volume or managed Postgres) |
| Memory | SQL (default) or JSON | `MEMORY_BACKEND=sql` + `DATABASE_URL`, or `MEMORY_STORE_PATH` | SQL: yes; JSON: yes if volume | **Yes** |
| Knowledge documents / vectors | JSON | `KNOWLEDGE_DOCUMENTS_PATH`, `KNOWLEDGE_STORE_PATH` | Yes if volume | **Yes** |
| Knowledge-core feedback | JSONL | under knowledge-core data dir | Yes if volume | **Yes** |
| Profiles | JSON | `PROFILE_STORE_PATH` | Yes if volume | **Yes** |
| Tokens / credits | JSON | `TOKEN_STORE_PATH` | Yes if volume | **Yes** |
| Billing store | JSON | `BILLING_STORE_PATH` | Yes if volume | **Yes** |
| Plugins state + crypto key | JSON + key file | `PLUGIN_STORE_PATH`, `PLUGIN_KEY_PATH` | Yes if volume | **Yes** |
| Plugin workspaces | Files | `PLUGIN_WORKSPACE_DIR` | Yes if volume | **Yes** |
| Attachments | In-memory + TTL files | `ATTACHMENT_STORAGE_DIR` | **No** (TTL / process) | Optional (temp only) |
| Videos | Files | `VIDEO_STORAGE_DIR` | Yes if volume | If video enabled |
| Agent / build workspace | Files | `AGENT_WORKSPACE_DIR` | Yes if volume | Recommended |
| Autonomous workflows | **In-memory** | process RAM | **No** | N/A — disable for public v1 (`WORKFLOWS_ENABLED=false`) |
| Legacy `/api/v1/workflow` orchestrator | **In-memory / request-scoped** | — | **No** | Same flag |
| Passkey challenges | In-memory map inside AuthStore (also flushed to JSON) | with auth store | Challenge TTL short | With auth volume |
| API / auth rate limiters | In-process | — | **No** (counters reset) | Use edge limit (see `docs/EDGE_RATE_LIMITING.md`) |

## Mount recommendation

Mount a single persistent disk at `/app/data` and keep defaults under `data/…`.
Point `DATABASE_URL=sqlite:///data/nexa.db` at that mount, **or** use managed Postgres.

Render Free has **no** persistent disk → `NEXA_STORAGE_MODE=ephemeral` only.
