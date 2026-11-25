# Document context and cloud model routing

The Learning setting `allow_cloud_on_documents` controls whether content from
user attachments and retrieved Knowledge Base chunks may be sent to cloud
model providers.

## Default: disabled

When the setting is `false` (the default):

- Chat requests containing attachments or retrieved Knowledge Base chunks are
  routed through the gateway's local-only model policy.
- Agent and orchestrator requests that include extracted document context use
  the same local-only policy.
- The local-only route overrides a saved manual cloud-model selection.
- Cloud fallback is disabled for these requests.
- If no suitable local model is available, the request fails instead of sending
  document content to a cloud provider.

## Explicit opt-in

An administrator may set `allow_cloud_on_documents=true` in Learning settings.
Normal model selection and fallback behavior then apply to requests containing
document context. Users should only enable this when the configured cloud
provider and its data-handling terms are acceptable for the documents involved.

This control does not change ordinary requests that contain no attachment or
retrieved Knowledge Base context.
