# HEXA 4.5 — first server-backed model

This milestone adds a dedicated HEXA provider adapter to the NEXA model
gateway. It does not claim that new model weights have been trained.

## Inference server

The initial adapter uses the Ollama-compatible chat protocol:
- `POST /api/chat` for generation and streaming
- `GET /` for health checks

Configure the backend:

```dotenv
AI_PROVIDER=hexa
HEXA_MODEL_URL=http://127.0.0.1:11434
HEXA_MODEL_NAME=hexa-4.5
REQUEST_TIMEOUT_SECONDS=60
```

For a remote server, use a private HTTPS endpoint. Do not expose an
unauthenticated inference port to the public internet; use a firewall or
authenticated private network.

The inference server must have a model installed under the exact
`HEXA_MODEL_NAME`. Before that happens, the adapter is only the serving
integration—not an independently trained foundation model.
