/**
 * Thin fetch-based client for the NEXA backend (see ../../../app for the
 * FastAPI implementation). No API keys ever live here or in any other
 * frontend file - the backend alone holds provider credentials.
 */
import type { AgentStepView, BackendStatus, GatewayModelCard, GatewayModelsResponse, ModelInfo } from "./types";
import { authHeaders } from "./session-token";
// Undefined → local backend. Empty string → same-origin (production behind Caddy).
// Electron serves its UI on localhost; use the same hostname for the API so SameSite=Lax cookies are sent.
const _apiBase = process.env.NEXT_PUBLIC_API_BASE_URL;
function resolveApiBase(): string {
  if (_apiBase && _apiBase.trim()) return _apiBase.replace(/\/$/, "");
  if (typeof window !== "undefined") {
    const port = window.location.port;
    // Next.js (dev/start) proxies /api → FastAPI. Electron static on 48420 does not.
    if (port === "4820" || port === "3000") return "";
    if (port === "48420") return "http://localhost:8420";
  }
  if (_apiBase === "") return "";
  return "http://127.0.0.1:8420";
}
export const API_BASE_URL = resolveApiBase();
export class ApiError extends Error {
  status: number;
  code: string;
  retryAfterSeconds?: number;
  constructor(status: number, code: string, message: string, retryAfterSeconds?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      credentials: "include",
      headers: authHeaders({
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      }),
    });
  } catch (cause) {
    if ((cause as Error)?.name === "AbortError") throw cause;
    throw new ApiError(0, "NetworkError", "Could not reach the NEXA backend. Is it running?");
  }
  if (!response.ok) {
    let code = "HTTPError";
    let message = `Request failed with status ${response.status}.`;
    let retryAfterSeconds: number | undefined;
    try {
      const body = await response.json();
      code = body.error ?? code;
      message = body.message ?? message;
      if (typeof body.retry_after_seconds === "number") {
        retryAfterSeconds = body.retry_after_seconds;
      }
    } catch {
      // response body wasn't JSON - keep the generic message above.
    }
    throw new ApiError(response.status, code, message, retryAfterSeconds);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
export function getHealth(signal?: AbortSignal) {
  return request<{ status: string; version?: string; storage_mode?: string }>(
    "/health",
    { signal }
  );
}
export function getStatus(signal?: AbortSignal) {
  return request<BackendStatus>("/api/v1/status", { signal });
}
export function getModel(signal?: AbortSignal) {
  return request<ModelInfo>("/api/v1/model", { signal });
}
export interface ChatApiMessage {
  role: "user" | "assistant" | "system";
  content: string;
}
export interface ChatCitationApi {
  index: number;
  document_id: string;
  filename: string;
  source: string;
  page?: number | null;
  section?: string | null;
}
export interface ChatApiResponse {
  message: string;
  provider: string;
  model: string;
  display_name?: string | null;
  fallback_used?: boolean;
  fallback_from?: string | null;
  task_kind?: string | null;
  selection_mode?: string | null;
  attachments_used?: string[];
  citations?: ChatCitationApi[];
  knowledge_used?: boolean;
  latency_ms: number;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  created_at: string;
}
export function sendChat(
  message: string,
  history: ChatApiMessage[],
  signal?: AbortSignal,
  options?: {
    task?: string;
    attachmentIds?: string[];
    applyPersonalization?: boolean;
    projectPersonalization?: Record<string, unknown> | null;
    useKnowledgeBase?: boolean;
    knowledgeConversationId?: string;
    knowledgeProjectId?: string;
    onDelta?: (chunk: string) => void;
    onFirstToken?: (ttftMs: number) => void;
  },
) {
  return streamChat(message, history, signal, options);
}
/** Read the existing SSE chat stream and surface each token as it arrives. */
export async function streamChat(
  message: string,
  history: ChatApiMessage[],
  signal?: AbortSignal,
  options?: {
    task?: string;
    attachmentIds?: string[];
    applyPersonalization?: boolean;
    projectPersonalization?: Record<string, unknown> | null;
    useKnowledgeBase?: boolean;
    knowledgeConversationId?: string;
    knowledgeProjectId?: string;
    onDelta?: (chunk: string) => void;
    onFirstToken?: (ttftMs: number) => void;
  },
): Promise<ChatApiResponse & { ttft_ms?: number; total_ms?: number }> {
  const started = performance.now();
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/chat/stream`, {
      method: "POST",
      signal,
      credentials: "include",
      headers: authHeaders({
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      }),
      body: JSON.stringify({
        message,
        history,
        task: options?.task,
        attachment_ids: options?.attachmentIds ?? [],
        apply_personalization: options?.applyPersonalization ?? true,
        project_personalization: options?.projectPersonalization ?? null,
        ...(options?.useKnowledgeBase != null
          ? { use_knowledge_base: options.useKnowledgeBase }
          : {}),
        ...(options?.knowledgeConversationId
          ? { knowledge_conversation_id: options.knowledgeConversationId }
          : {}),
        ...(options?.knowledgeProjectId
          ? { knowledge_project_id: options.knowledgeProjectId }
          : {}),
      }),
    });
  } catch (cause) {
    if ((cause as Error)?.name === "AbortError") throw cause;
    throw new ApiError(0, "NetworkError", "Could not reach the NEXA backend. Is it running?");
  }
  if (!response.ok || !response.body) {
    let code = "HTTPError";
    let messageText = `Request failed with status ${response.status}.`;
    try {
      const body = await response.json();
      code = body.error ?? code;
      messageText = body.message ?? messageText;
    } catch {
      // body was not JSON
    }
    throw new ApiError(response.status, code, messageText);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let text = "";
  let clientTtft: number | undefined;
  let serverTtft: number | undefined;
  let serverTotal: number | undefined;
  let donePayload: Partial<ChatApiResponse> = {};
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const line = frame.split("\n").find((item) => item.startsWith("data:"));
      if (!line) continue;
      const event = JSON.parse(line.slice(5).trim()) as {
        type: string;
        text?: string;
        error?: string;
        message?: string;
        provider?: string;
        model?: string;
        display_name?: string | null;
        fallback_used?: boolean;
        fallback_from?: string | null;
        task_kind?: string | null;
        selection_mode?: string | null;
        ttft_ms?: number | null;
        total_ms?: number | null;
        citations?: ChatCitationApi[];
        knowledge_used?: boolean;
      };
      if (event.type === "error") {
        throw new ApiError(502, event.error ?? "ModelError", event.message ?? "The model failed.");
      }
      if (event.type === "delta" && event.text) {
        if (clientTtft === undefined) {
          clientTtft = Math.round(performance.now() - started);
          options?.onFirstToken?.(clientTtft);
        }
        text += event.text;
        options?.onDelta?.(event.text);
      }
      if (event.type === "done") {
        if (typeof event.ttft_ms === "number") serverTtft = event.ttft_ms;
        if (typeof event.total_ms === "number") serverTotal = event.total_ms;
        donePayload = {
          provider: event.provider ?? "",
          model: event.model ?? "",
          display_name: event.display_name,
          fallback_used: event.fallback_used,
          fallback_from: event.fallback_from,
          task_kind: event.task_kind,
          selection_mode: event.selection_mode,
          citations: event.citations,
          knowledge_used: event.knowledge_used,
        };
      }
    }
  }
  return {
    message: text,
    provider: donePayload.provider ?? "",
    model: donePayload.model ?? "",
    display_name: donePayload.display_name,
    fallback_used: donePayload.fallback_used,
    fallback_from: donePayload.fallback_from,
    task_kind: donePayload.task_kind,
    selection_mode: donePayload.selection_mode,
    citations: donePayload.citations,
    knowledge_used: donePayload.knowledge_used,
    latency_ms: Math.round(performance.now() - started),
    ttft_ms: serverTtft ?? clientTtft,
    total_ms: serverTotal ?? Math.round(performance.now() - started),
    created_at: new Date().toISOString(),
  };
}
// --- Research mode (live web search + cited synthesis) ---------------------
export interface ResearchSourceApi {
  url: string;
  title: string;
  text: string;
  content_hash: string;
}
export interface ResearchChatApiResponse {
  message: string;
  provider: string;
  model: string;
  display_name?: string | null;
  sources: ResearchSourceApi[];
  latency_ms: number;
}
export function researchChat(message: string, signal?: AbortSignal, maxResults = 5) {
  return request<ResearchChatApiResponse>("/api/v1/research/chat", {
    method: "POST",
    body: JSON.stringify({ message, max_results: maxResults }),
    signal,
  });
}
// --- Create mode (image generation) -----------------------------------------
export interface ImageGenerationApiResponse {
  provider: string;
  model: string;
  images: string[];
  format: "url" | "b64_json";
  metadata?: Record<string, unknown>;
}
export function generateImage(prompt: string, signal?: AbortSignal) {
  return request<ImageGenerationApiResponse>("/api/v1/image/generate", {
    method: "POST",
    body: JSON.stringify({ prompt }),
    signal,
  });
}

// --- Image-to-video ---------------------------------------------------------
export interface VideoJobApiResponse {
  job_id: string;
  phase: string;
  progress: number;
  message: string;
  intent: string;
  video_url?: string | null;
  provider?: string | null;
  model?: string | null;
  motion_plan?: {
    scene_summary: string;
    motion_prompt: string;
    conservative: boolean;
    source: string;
  } | null;
  error?: string | null;
}

export function detectVideoIntent(prompt: string, hasImage: boolean, signal?: AbortSignal) {
  return request<{ intent: string | null; matched: boolean }>("/api/v1/video/intent", {
    method: "POST",
    body: JSON.stringify({ prompt, has_image: hasImage }),
    signal,
  });
}

export interface BuildRunApiResponse {
  success: boolean;
  mode: "create" | "edit";
  project_id: string | null;
  slug: string | null;
  root_path: string | null;
  files_created: string[];
  files_modified: string[];
  preview_url: string | null;
  steps: { name: string; status: string; detail: string; tool?: string | null }[];
  message: string;
  error: string | null;
  /** V2 user-safe plan snapshot (no chain-of-thought). */
  plan?: {
    project_id: string;
    name: string;
    type: string;
    goal: string;
    stack: string;
    architecture: string;
    files: string[];
    features: string[];
    status: string;
    preview: string | null;
  } | null;
  status?: string | null;
  engine_version?: string;
}

/** Client-side BUILD_PROJECT intent — mirrors backend `app/build/intents.py`. */
export function isBuildProjectIntent(text: string, hasActiveBuildProject = false): boolean {
  const stripped = text.trim();
  if (!stripped) return false;
  if (/(пример\s+код|sample\s+code|example\s+(of\s+)?code|snippet|как\s+написать|how\s+to\s+write|объясни\s+код)/i.test(stripped)) {
    return false;
  }
  const isNew =
    /(создай|сделай|собери|напиши)\s+(мне\s+)?(?:\S+\s+){0,4}(игру|игрушку|гонку|гоночн\w*|сайт|приложен\w*|инструмент|прототип|программ\w*|проект|api|бот|3\s*d|three\.?js|танк\w*|пол[её]т\w*|приключен\w*)/i.test(
      stripped,
    ) ||
    /create\s+(an?\s+|me\s+a\s+)?(?:\S+\s+){0,4}(app|game|website|site|tool|prototype|program|project|racing|racer|flight|tank|adventure)/i.test(
      stripped,
    ) ||
    /build\s+(an?\s+|me\s+a\s+)?(?:\S+\s+){0,4}(app|game|website|site|tool|project|racing|racer|flight|tank)/i.test(
      stripped,
    ) ||
    /(сделай|создай)\s+мне\b/i.test(stripped) ||
    /и\s+запусти/i.test(stripped) ||
    /working\s+project|полный\s+проект/i.test(stripped);
  if (isNew) return true;
  if (!hasActiveBuildProject) return false;
  return (
    /^(добавь|измени|исправь|улучши|сделай(?:\s+\S+){0,4}\s+(красивее|быстрее|больше)|add\s+|change\s+|fix\s+|improve\s+|make\s+(it\s+)?|поменяй|увеличь|уменьши|перепиши)/i.test(
      stripped,
    ) || /(game\s*over|систем\w*\s+очк|очк\w*|score|rival|соперник|карт\w*|bigger\s*map)/i.test(stripped)
  );
}

export function runBuild(
  message: string,
  options?: { conversationId?: string; projectId?: string | null; signal?: AbortSignal },
) {
  return request<BuildRunApiResponse>("/api/v1/build/run", {
    method: "POST",
    body: JSON.stringify({
      message,
      conversation_id: options?.conversationId ?? null,
      project_id: options?.projectId ?? null,
    }),
    signal: options?.signal,
  });
}

export function resolveBuildPreviewUrl(previewPath: string | null | undefined): string | null {
  if (!previewPath) return null;
  if (/^https?:\/\//i.test(previewPath)) return previewPath;
  return `${API_BASE_URL}${previewPath.startsWith("/") ? "" : "/"}${previewPath}`;
}

export interface BuildProjectApi {
  project_id: string;
  slug: string;
  title: string;
  status: string;
  entry_file: string;
  files: string[];
  preview_url: string | null;
  stack: string | null;
  features: string[];
  root_rel: string;
}

export function getBuildProject(projectId: string, signal?: AbortSignal) {
  return request<BuildProjectApi>(`/api/v1/build/projects/${projectId}`, { signal });
}

export function resolveBuildExportUrl(projectId: string): string {
  return `${API_BASE_URL}/api/v1/build/export/${projectId}`;
}

/** Fetch a preview file as text (same sandbox as iframe). */
export async function fetchBuildPreviewText(
  projectId: string,
  filePath: string,
  signal?: AbortSignal,
): Promise<string> {
  const url = resolveBuildPreviewUrl(`/api/v1/build/preview/${projectId}/${filePath}`);
  if (!url) throw new ApiError(0, "PreviewError", "Missing preview URL");
  const res = await fetch(url, { signal, credentials: "include" });
  if (!res.ok) throw new ApiError(res.status, "PreviewError", `Preview fetch failed: ${filePath}`);
  return res.text();
}

export function startImageToVideo(prompt: string, attachmentIds: string[], signal?: AbortSignal) {
  return request<VideoJobApiResponse>("/api/v1/video/image-to-video", {
    method: "POST",
    body: JSON.stringify({ prompt, attachment_ids: attachmentIds, force: true }),
    signal,
  });
}

export function getVideoJob(jobId: string, signal?: AbortSignal) {
  return request<VideoJobApiResponse>(`/api/v1/video/jobs/${jobId}`, { signal });
}

export function resolveMediaUrl(pathOrUrl: string): string {
  if (/^https?:\/\//i.test(pathOrUrl) || pathOrUrl.startsWith("data:")) return pathOrUrl;
  if (pathOrUrl.startsWith("/")) return `${API_BASE_URL}${pathOrUrl}`;
  return `${API_BASE_URL}/${pathOrUrl}`;
}

export function getGatewayModels(signal?: AbortSignal) {
  return request<GatewayModelsResponse>("/api/v1/models", { signal });
}
export function updateModelSelection(body: { provider: string; model: string; allow_fallback: boolean }) {
  return request<GatewayModelsResponse>("/api/v1/models/selection", {
    method: "PUT",
    body: JSON.stringify(body),
  });
}
export function checkModel(model: string, live = true) {
  return request<GatewayModelCard>("/api/v1/models/check", {
    method: "POST",
    body: JSON.stringify({ model, live }),
  });
}
export interface AgentApiResponse {
  task_id: string;
  status: string;
  success: boolean;
  final_answer: string | null;
  steps: {
    index: number;
    step_type: "tool_call" | "final_answer" | "error";
    tool_name: string | null;
    tool_input: Record<string, unknown>;
    output: unknown;
    success: boolean;
    error: string | null;
    dry_run: boolean;
    timestamp: string;
  }[];
  elapsed_ms: number;
  dry_run: boolean;
  provider?: string | null;
  model?: string | null;
  display_name?: string | null;
  project_status?: string | null;
  project_id?: string | null;
  project_manifest?: Record<string, unknown> | null;
  partial_success?: boolean;
}

/** Collect verified download links from agent tool outputs (never invent URLs). */
export function extractAgentDownloadLinks(response: AgentApiResponse): {
  filename: string;
  download_url: string;
  file_id?: string;
}[] {
  const links: { filename: string; download_url: string; file_id?: string }[] = [];
  const seen = new Set<string>();
  for (const step of response.steps) {
    if (!step.success || !step.output || typeof step.output !== "object") continue;
    const out = step.output as Record<string, unknown>;
    const url = typeof out.download_url === "string" ? out.download_url : "";
    if (!url.startsWith("/api/v1/results/")) continue;
    if (seen.has(url)) continue;
    seen.add(url);
    links.push({
      filename: typeof out.filename === "string" ? out.filename : "file",
      download_url: url,
      file_id: typeof out.file_id === "string" ? out.file_id : undefined,
    });
  }
  return links;
}
export function runAgent(
  task: string,
  dryRun: boolean,
  signal?: AbortSignal,
  attachmentIds?: string[],
  disabledTools?: string[],
) {
  return request<AgentApiResponse>("/api/v1/agent", {
    method: "POST",
    body: JSON.stringify({
      task,
      dry_run: dryRun,
      attachment_ids: attachmentIds ?? [],
      disabled_tools: disabledTools ?? [],
    }),
    signal,
  });
}
export function toAgentStepViews(response: AgentApiResponse): AgentStepView[] {
  return response.steps.map((s) => ({
    index: s.index,
    stepType: s.step_type,
    toolName: s.tool_name,
    toolInput: s.tool_input,
    output: s.output,
    success: s.success,
    error: s.error,
    dryRun: s.dry_run,
  }));
}
export interface MemoryItemApi {
  id: string;
  type: string;
  content: string;
  tags: string[];
  metadata: Record<string, unknown>;
  user_id: string | null;
  created_at: string;
  updated_at: string;
}
export interface MemorySearchResponse {
  results: { item: MemoryItemApi; score: number }[];
  count: number;
}
export function listMemory(
  params: { query?: string; type?: string; limit?: number } = {},
  signal?: AbortSignal
) {
  const search = new URLSearchParams();
  if (params.query) search.set("query", params.query);
  if (params.type) search.set("type", params.type);
  if (params.limit) search.set("limit", String(params.limit));
  const qs = search.toString();
  return request<MemorySearchResponse>(`/api/v1/memory${qs ? `?${qs}` : ""}`, { signal });
}
export interface MemoryCreateResultApi {
  item: MemoryItemApi | null;
  saved: boolean;
  contradictions: {
    existing_id: string;
    existing_content: string;
    new_content: string;
    reason: string;
  }[];
}
export function createMemory(
  item: {
    content: string;
    type?: string;
    tags?: string[];
    metadata?: Record<string, unknown>;
    force?: boolean;
    replace_id?: string;
  },
  signal?: AbortSignal
) {
  return request<MemoryCreateResultApi>("/api/v1/memory", {
    method: "POST",
    body: JSON.stringify(item),
    signal,
  });
}
export function updateMemory(
  id: string,
  item: { content?: string; type?: string; tags?: string[]; metadata?: Record<string, unknown> },
  signal?: AbortSignal,
) {
  return request<MemoryItemApi>(`/api/v1/memory/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(item),
    signal,
  });
}
export function deleteMemory(id: string, signal?: AbortSignal) {
  return request<{ deleted: boolean; id: string }>(`/api/v1/memory/${encodeURIComponent(id)}`, {
    method: "DELETE",
    signal,
  });
}

export function clearMemory(type?: string, signal?: AbortSignal) {
  const query = type ? `?type=${encodeURIComponent(type)}` : "";
  return request<{ cleared: number }>(`/api/v1/memory${query}`, {
    method: "DELETE",
    signal,
  });
}
// --- Knowledge Base / RAG (Part 9) ------------------------------------------
export interface KnowledgeDocumentApi {
  id: string;
  filename: string;
  source_type: "upload" | "desktop_file" | "web_research" | "note";
  source: string;
  format: string;
  size_bytes: number;
  status: "processing" | "ready" | "error";
  error: string | null;
  chunk_count: number;
  project_id: string | null;
  conversation_id: string | null;
  created_at: string;
}
export function listKnowledgeDocuments(projectId?: string, signal?: AbortSignal) {
  const qs = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  return request<KnowledgeDocumentApi[]>(`/api/v1/knowledge/documents${qs}`, { signal });
}
export async function uploadKnowledgeDocument(file: File, projectId?: string) {
  const formData = new FormData();
  formData.append("file", file);
  if (projectId) formData.append("project_id", projectId);
  // Deliberately bypasses `request()`: it always sets a JSON Content-Type,
  // but a multipart body needs the browser to set its own boundary.
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/knowledge/documents`, {
      method: "POST",
      body: formData,
      credentials: "include",
      headers: authHeaders(),
    });
  } catch {
    throw new ApiError(0, "NetworkError", "Could not reach the NEXA backend. Is it running?");
  }
  if (!response.ok) {
    let code = "HTTPError";
    let message = `Request failed with status ${response.status}.`;
    try {
      const body = await response.json();
      code = body.error ?? code;
      message = body.message ?? message;
    } catch {
      // keep the generic message
    }
    throw new ApiError(response.status, code, message);
  }
  return (await response.json()) as KnowledgeDocumentApi;
}
export function addKnowledgeNote(title: string, text: string, projectId?: string) {
  return request<KnowledgeDocumentApi>("/api/v1/knowledge/notes", {
    method: "POST",
    body: JSON.stringify({ title, text, project_id: projectId }),
  });
}
export function deleteKnowledgeDocument(id: string) {
  return request<{ deleted: boolean; id: string }>(`/api/v1/knowledge/documents/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}
export interface WorkflowTaskApi {
  id: string;
  name: string;
  description: string;
  status: string;
  agent: string;
  error: string | null;
}
export interface WorkflowApprovalApi {
  task_id: string;
  agent: string;
  action: string;
  resources: string[];
  consequences: string;
}
export interface WorkflowApi {
  id: string;
  name: string;
  description: string;
  goal: string;
  autonomy: string;
  status: string;
  progress: number;
  current_task: string | null;
  error: string | null;
  final_result: string | null;
  sources: string[];
  pending_approval: WorkflowApprovalApi | null;
  checkpoints: { name: string; completed_task_ids: string[] }[];
  tasks: WorkflowTaskApi[];
}
export function listWorkflows() {
  return request<WorkflowApi[]>("/api/v1/workflows");
}
export function createWorkflow(goal: string, autonomy: string, name?: string) {
  return request<WorkflowApi>("/api/v1/workflows", {
    method: "POST",
    body: JSON.stringify({ goal, autonomy, name }),
  });
}
export function workflowAction(id: string, action: "start" | "pause" | "resume" | "cancel" | "approve" | "reject") {
  return request<WorkflowApi>(`/api/v1/workflows/${encodeURIComponent(id)}/${action}`, { method: "POST" });
}

export interface PluginActionApi {
  name: string;
  description: string;
  permissions: string[];
  dangerous: boolean;
  input_schema: Record<string, unknown>;
}

export interface PluginCardApi {
  id: string;
  version: string;
  name: string;
  description: string;
  category: string;
  integration_type: string;
  dependencies: string[];
  required_permissions: string[];
  optional_permissions: string[];
  timeout_seconds: number;
  actions: PluginActionApi[];
  install_hint: string;
  status: string;
  enabled: boolean;
  granted_permissions: string[];
  settings: Record<string, unknown>;
  has_token: boolean;
  last_error: string | null;
  last_probe: string | null;
  connected_at: string | null;
}

export function listHubPlugins(query = "", category = "", signal?: AbortSignal) {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (category) params.set("category", category);
  const qs = params.toString();
  return request<{ plugins: PluginCardApi[]; count: number }>(
    `/api/v1/plugins${qs ? `?${qs}` : ""}`,
    { signal },
  );
}

export function getHubPlugin(id: string, signal?: AbortSignal) {
  return request<PluginCardApi>(`/api/v1/plugins/${encodeURIComponent(id)}`, { signal });
}

export function connectHubPlugin(
  id: string,
  body: { permissions?: string[]; token?: string; settings?: Record<string, unknown> },
) {
  return request<PluginCardApi>(`/api/v1/plugins/${encodeURIComponent(id)}/connect`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function disconnectHubPlugin(id: string) {
  return request<PluginCardApi>(`/api/v1/plugins/${encodeURIComponent(id)}/disconnect`, {
    method: "POST",
  });
}

export function diagnoseHubPlugin(id: string) {
  return request<{ plugin_id: string; probe: Record<string, unknown> }>(
    `/api/v1/plugins/${encodeURIComponent(id)}/diagnose`,
    { method: "POST" },
  );
}

export function invokeHubPlugin(
  id: string,
  body: { action: string; params?: Record<string, unknown>; confirm?: boolean },
) {
  return request<{ plugin_id: string; result: { success: boolean; output: unknown; error: string | null } }>(
    `/api/v1/plugins/${encodeURIComponent(id)}/invoke`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export function patchHubPluginPermissions(id: string, permissions: string[]) {
  return request<PluginCardApi>(`/api/v1/plugins/${encodeURIComponent(id)}/permissions`, {
    method: "PATCH",
    body: JSON.stringify({ permissions }),
  });
}
