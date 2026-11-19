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
| Image attachments | Image bytes + atomic owner manifest (`<id>.meta.json`) | `ATTACHMENT_STORAGE_DIR` | Yes until TTL if volume is persistent; owner and signature are revalidated on restore | **Yes** for restart survival |
| Document attachments | Extracted text/chunks in memory; source file deleted after parsing | `ATTACHMENT_STORAGE_DIR` | **No** — intentionally expires on process restart | No; do not treat as durable document storage |
| Videos | Files + atomic `.nexa_video_jobs.json` owner/status manifest | `VIDEO_STORAGE_DIR` | Completed local videos and owner ACL survive restart if volume is persistent; interrupted jobs become failed; signed provider URLs are not persisted | **Yes** if video enabled |
| Agent / build workspace | Files | `AGENT_WORKSPACE_DIR` | Yes if volume | Recommended |
| Autonomous workflows | **In-memory** | process RAM | **No** | N/A — disable for public v1 (`WORKFLOWS_ENABLED=false`) |
| Legacy `/api/v1/workflow` orchestrator | **In-memory / request-scoped** | — | **No** | Same flag |
| Passkey challenges | In-memory map inside AuthStore (also flushed to JSON) | with auth store | Challenge TTL short | With auth volume |
| API / auth rate limiters | In-process | — | **No** (counters reset) | Use edge limit (see `docs/EDGE_RATE_LIMITING.md`) |

## Mount recommendation

Mount a single persistent disk at `/app/data` and keep defaults under `data/…`.
Point `DATABASE_URL=sqlite:///data/nexa.db` at that mount, **or** use managed Postgres.

Render Free has **no** persistent disk → `NEXA_STORAGE_MODE=ephemeral` only.

## Media restart and deletion semantics

- Image attachments persist only their bounded public metadata and ownership manifest; raw image bytes stay in the dedicated attachment directory. Expired, invalid, signature-mismatched, and orphaned image files are removed when the manager starts or runs TTL cleanup.
- Document attachments are deliberately transient: extracted text/chunks remain in process memory, and raw source files are deleted after parsing. Re-upload after a process restart is required.
- Video job manifests store the owner, safe status fields, provider/model labels, and only a validated local video URL. Motion prompts, image descriptions, provider error details, and signed remote URLs are excluded.
- A job that was active during a restart is marked failed rather than pretending it resumed. Account deletion removes manifest entries and the user's tracked local video files.
- These JSON manifests are designed for the documented single-process deployment. They are not a distributed transaction store and do not make multiple replicas safe.
