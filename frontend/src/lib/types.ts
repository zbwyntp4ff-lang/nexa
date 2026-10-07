/** Shared frontend types for NEXA AI. */
export type AppMode = "chat" | "agent" | "code" | "research" | "create" | "vision";
/** Modes with a real, connected backend in this build. Others render "Coming Soon". */
export const AVAILABLE_MODES: ReadonlySet<AppMode> = new Set([
  "chat",
  "agent",
  "code",
  "research",
  "create",
  "vision",
]);
export interface ModeDefinition {
  id: AppMode;
  label: string;
  description: string;
}
export const MODES: ModeDefinition[] = [
  { id: "chat", label: "Chat", description: "Talk with NEXA" },
  { id: "agent", label: "Agent", description: "Plan and execute multi-step tasks with tools" },
  { id: "code", label: "Code", description: "Chat, tuned for reading and writing code" },
  { id: "research", label: "Research", description: "Search the web and cite sources" },
  { id: "create", label: "Create", description: "Generate images from a prompt" },
  { id: "vision", label: "Vision", description: "Understand and describe images" },
];
export type MessageRole = "user" | "assistant" | "system";
export interface AgentStepView {
  index: number;
  stepType: "tool_call" | "final_answer" | "error";
  toolName: string | null;
  toolInput: Record<string, unknown>;
  output: unknown;
  success: boolean;
  error: string | null;
  dryRun: boolean;
}
export type AttachmentKind = "image" | "document";
export type AttachmentUploadStatus = "uploading" | "processing" | "ready" | "failed";
export interface AttachmentView {
  /** Stable client-side id, used as the React key and for progress updates. */
  id: string;
  /** The id returned by `POST /api/v1/attachments` once upload+processing succeeds. */
  serverId?: string;
  name: string;
  size: number;
  mimeType: string;
  kind: AttachmentKind;
  status: AttachmentUploadStatus;
  /** 0-100 upload byte progress; irrelevant once status is "ready"/"failed". */
  progress: number;
  error?: string;
  /** Local object URL for an image preview thumbnail (images only). */
  previewUrl?: string;
  charCount?: number;
  pageCount?: number;
}
export interface AttachmentUploadOutcome {
  id: string;
  kind: AttachmentKind;
  status: "ready" | "failed";
  error?: string;
  charCount?: number;
  pageCount?: number;
}
export interface CitationView {
  index: number;
  url: string;
  title: string;
}
export interface GeneratedImageView {
  url: string;
  base64?: string;
  format: "url" | "b64_json";
}
export interface GeneratedVideoView {
  url: string;
  provider?: string;
  model?: string;
  motionPrompt?: string;
}
export interface ChatMessageView {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: string;
  mode: AppMode;
  attachments?: AttachmentView[];
  /** Present only for assistant messages produced by Agent mode. */
  agentSteps?: AgentStepView[];
  /** Provider and model that actually produced this answer, when the backend reports one. */
  modelLabel?: string;
  /** Present only for assistant messages produced by Research mode: numbered web sources. */
  citations?: CitationView[];
  /** Present only for assistant messages produced by Create mode: generated image results. */
  generatedImages?: GeneratedImageView[];
  /** Present for IMAGE_TO_VIDEO results shown inline in chat history. */
  generatedVideos?: GeneratedVideoView[];
  /** Streaming progress text while a video job runs. */
  progressLabel?: string;
  /** Present only for assistant messages that errored. */
  error?: string;
  pending?: boolean;
  /** Debug latency (ms) — shown only when NEXA debug latency is enabled. */
  latency?: { ttftMs?: number; totalMs?: number };
}
export interface Conversation {
  id: string;
  title: string;
  mode: AppMode;
  messages: ChatMessageView[];
  projectId: string | null;
  /** Active BUILD_PROJECT workspace id (agent_workspace/builds/...), if any. */
  buildProjectId?: string | null;
  createdAt: string;
  updatedAt: string;
}
export interface Project {
  id: string;
  name: string;
  instructions: string;
  fileNames: string[];
  createdAt: string;
}
export type AppStatus = "online" | "offline" | "thinking" | "using_tool" | "researching" | "generating" | "error";
export interface BackendStatus {
  status: string;
  app_name: string;
  environment: string;
  provider: string;
  provider_healthy: boolean;
}
export interface ModelInfo {
  provider: string;
  model: string;
  display_name?: string | null;
  selection_mode?: string;
  allow_fallback?: boolean;
  availability?: string | null;
  availability_reason?: string | null;
  last_provider?: string | null;
  last_model?: string | null;
  last_display_name?: string | null;
}
export interface GatewayModelCard {
  provider: string;
  model_id: string;
  display_name: string;
  capabilities: string[];
  context_window: number | null;
  supports_vision: boolean;
  supports_tools: boolean;
  supports_streaming: boolean;
  availability: string;
  availability_reason: string | null;
}
export interface GatewayModelsResponse {
  selection_mode: string;
  provider: string | null;
  model: string | null;
  allow_fallback: boolean;
  active_provider: string;
  active_model: string;
  active_display_name: string | null;
  availability: string | null;
  availability_reason: string | null;
  last_provider: string | null;
  last_model: string | null;
  last_display_name: string | null;
  models: GatewayModelCard[];
}
