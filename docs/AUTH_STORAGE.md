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
