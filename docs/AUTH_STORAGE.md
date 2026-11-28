# Auth storage durability

Auth users, sessions, and passkey challenge records use the JSON file store at
`AUTH_STORE_PATH` (default `data/auth_store.json`).

This is **durable across process restarts** when the path is on a persistent
volume (Docker/Render disk, host mount, etc.). It is **not** a separate SQL
backend — conversations and memory already use `DATABASE_URL` SQL.

Full component map: [`docs/STORAGE_MATRIX.md`](STORAGE_MATRIX.md).

## Operator requirements for multi-user cloud

1. Mount a persistent volume for `AUTH_STORE_PATH` (and related JSON stores:
   profiles, tokens, plugins, knowledge documents).
2. Set `DATABASE_URL` to SQLite on that volume or PostgreSQL.
3. Set `MEMORY_BACKEND=sql` (default) and `TOKENS_ENFORCE=true`.
4. For durable public hosts set `NEXA_STORAGE_MODE=persistent` so startup
   **refuses** `TOKENS_ENFORCE=false` and other unsafe defaults.

A second auth SQL system was intentionally not added; migrating auth to SQL is
optional future work if you need multi-instance shared auth without sticky
volumes.


## Registration burst capacity

The API accepts a launch burst of up to 100 registrations from one shared IP:
`REGISTER_RATE_LIMIT_PER_HOUR` defaults to `150` to allow for retries while
preserving an hourly anti-abuse limit. Deployment examples also set `API_RATE_LIMIT_PER_MINUTE=150`; the global
API middleware otherwise could reject a shared-IP burst before the registration
route's own limit is reached.  The registration route runs password
hashing and file persistence in Starlette's worker thread pool so CPU/disk work
does not block the ASGI event loop.

The current JSON auth store is designed for **one API process/container with a
persistent volume**. Its lock is process-local; do not scale this deployment
to multiple Uvicorn workers or multiple API replicas and expect cross-process
uniqueness guarantees. Multi-instance signup requires moving auth users,
sessions, verification records, and uniqueness constraints into shared
transactional SQL storage (PostgreSQL recommended). The 100-request regression
test validates concurrent requests against one API process; it is not a
production load test and does not prove capacity under arbitrary hardware.
