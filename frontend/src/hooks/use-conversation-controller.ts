"use client";
import * as React from "react";
import { toast } from "sonner";
import {
  ApiError,
  detectVideoIntent,
  generateImage,
  getVideoJob,
  isBuildProjectIntent,
  researchChat,
  resolveBuildPreviewUrl,
  resolveMediaUrl,
  runAgent,
  runBuild,
  sendChat,
  startImageToVideo,
  toAgentStepViews,
  type ChatApiMessage,
} from "@/lib/api";
import {
  AVAILABLE_MODES,
  type AppMode,
  type AttachmentView,
  type ChatMessageView,
  type CitationView,
  type GeneratedImageView,
  type GeneratedVideoView,
} from "@/lib/types";
import { disabledToolNames, pluginGatingMode } from "@/lib/plugins";
import { useChatStore } from "@/store/chat-store";
import { usePluginsStore } from "@/store/plugins-store";
import { useUiStore } from "@/store/ui-store";

const CODE_MODE_SYSTEM_PROMPT =
  "You are NEXA in Code mode. Prioritize correct, well-formatted code in fenced code blocks. " +
  "Explain your reasoning briefly, only when it adds value.";

function makeId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

interface RunForModeResult {
  content: string;
  agentSteps?: ChatMessageView["agentSteps"];
  modelLabel?: string;
  citations?: CitationView[];
  generatedImages?: GeneratedImageView[];
  generatedVideos?: GeneratedVideoView[];
  latency?: { ttftMs?: number; totalMs?: number };
}

/** Keep recent turns only — long histories slow local-model prefill/TTFT. */
const MAX_HISTORY_MESSAGES = 8;

function toHistory(messages: ChatMessageView[]): ChatApiMessage[] {
  return messages
    .filter((m) => (m.role === "user" || m.role === "assistant") && !m.pending && !m.error)
    .slice(-MAX_HISTORY_MESSAGES)
    .map((m) => ({ role: m.role, content: m.content }));
}

function isDebugLatencyEnabled(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem("nexa-debug-latency") === "1";
  } catch {
    return false;
  }
}

async function runImageToVideo(
  text: string,
  attachmentIds: string[],
  signal: AbortSignal,
  onProgress: (label: string, content: string) => void,
): Promise<RunForModeResult> {
  const started = await startImageToVideo(text, attachmentIds, signal);
  onProgress(started.message || "IMAGE_TO_VIDEO…", `IMAGE_TO_VIDEO · ${started.message || "starting"}`);
  let job = started;
  while (job.phase !== "ready" && job.phase !== "failed") {
    await new Promise((r) => setTimeout(r, 1500));
    if (signal.aborted) throw new DOMException("Aborted", "AbortError");
    job = await getVideoJob(job.job_id, signal);
    const label = `${job.progress}% · ${job.message || job.phase}`;
    onProgress(label, `IMAGE_TO_VIDEO · ${label}`);
  }
  if (job.phase === "failed" || job.error) {
    throw new ApiError(503, "VideoGenerationError", job.error || job.message || "Image-to-video failed.");
  }
  if (!job.video_url) {
    throw new ApiError(503, "VideoGenerationError", "Video job finished without a video URL.");
  }
  return {
    content: "Готово — вот оживление вашей картинки.",
    generatedVideos: [
      {
        url: resolveMediaUrl(job.video_url),
        provider: job.provider ?? undefined,
        model: job.model ?? undefined,
        motionPrompt: job.motion_plan?.motion_prompt,
      },
    ],
    modelLabel: job.provider && job.model ? `${job.provider} · ${job.model}` : undefined,
  };
}

/**
 * Owns the send/retry/edit/stop lifecycle for chat conversations.
 */
export function useConversationController() {
  const setStatus = useUiStore((s) => s.setStatus);
  const setActiveTool = useUiStore((s) => s.setActiveTool);
  const [isSending, setIsSending] = React.useState(false);
  const [sendingConversationId, setSendingConversationId] = React.useState<string | null>(null);
  const abortRef = React.useRef<AbortController | null>(null);

  const runForMode = React.useCallback(
    async (
      mode: AppMode,
      text: string,
      history: ChatApiMessage[],
      signal: AbortSignal,
      attachmentIds: string[],
      onDelta?: (chunk: string) => void,
    ): Promise<RunForModeResult> => {
      if (mode === "agent") {
        setStatus("using_tool");
        const disabledTools = disabledToolNames(usePluginsStore.getState().enabled);
        const response = await runAgent(text, false, signal, attachmentIds, disabledTools);
        return {
          content: response.final_answer ?? "(Agent finished without a final answer.)",
          agentSteps: toAgentStepViews(response),
          modelLabel: response.display_name
            ? `${response.provider} · ${response.display_name}`
            : undefined,
        };
      }
      if (mode === "research") {
        setStatus("researching");
        const response = await researchChat(text, signal);
        const citations: CitationView[] = response.sources.map((s, i) => ({
          index: i + 1,
          url: s.url,
          title: s.title,
        }));
        return {
          content: response.message,
          citations,
          modelLabel: response.display_name ? `${response.provider} · ${response.display_name}` : undefined,
        };
      }
      if (mode === "create") {
        setStatus("generating");
        const response = await generateImage(text, signal);
        const generatedImages: GeneratedImageView[] = response.images.map((img) => ({
          url: response.format === "url" ? img : "",
          base64: response.format === "b64_json" ? img : undefined,
          format: response.format,
        }));
        return {
          content: `Generated ${generatedImages.length} image${generatedImages.length === 1 ? "" : "s"} for: "${text}"`,
          generatedImages,
          modelLabel: `${response.provider} · ${response.model}`,
        };
      }
      setStatus("thinking");
      const fullHistory =
        mode === "code" ? [{ role: "system" as const, content: CODE_MODE_SYSTEM_PROMPT }, ...history] : history;
      const response = await sendChat(text, fullHistory, signal, {
        task: mode === "code" ? "coding" : undefined,
        attachmentIds,
        onDelta,
      });
      const modelLabel = response.display_name
        ? `${response.provider} · ${response.display_name}${response.fallback_used ? " · fallback" : ""}`
        : undefined;
      return {
        content: response.message,
        modelLabel,
        latency: {
          ttftMs: response.ttft_ms,
          totalMs: response.total_ms ?? response.latency_ms,
        },
      };
    },
    [setStatus],
  );

  const send = React.useCallback(
    async (conversationId: string, text: string, attachments?: AttachmentView[]) => {
      const { conversations, addMessage, updateMessage } = useChatStore.getState();
      const conversation = conversations.find((c) => c.id === conversationId);
      if (!conversation) return;
      const mode = conversation.mode;
      const gatingPlugin = pluginGatingMode(mode);
      const pluginOff = gatingPlugin ? !usePluginsStore.getState().enabled[gatingPlugin] : false;
      if (!AVAILABLE_MODES.has(mode) || pluginOff) {
        toast(pluginOff ? "This mode is turned off" : "This mode isn't connected yet", {
          description: pluginOff
            ? "Enable its plugin in Settings → Plugins to use it."
            : "Coming soon - no request was sent.",
        });
        return;
      }
      const trimmed = text.trim();
      if (!trimmed) return;
      const readyAttachments = (attachments ?? []).filter((a) => a.status === "ready" && a.serverId);
      const readyAttachmentIds = readyAttachments.map((a) => a.serverId as string);
      const hasImage = readyAttachments.some((a) => a.kind === "image");
      addMessage(conversationId, {
        id: makeId(),
        role: "user",
        content: trimmed,
        createdAt: new Date().toISOString(),
        mode,
        attachments,
      });
      const assistantId = makeId();
      addMessage(conversationId, {
        id: assistantId,
        role: "assistant",
        content: "",
        createdAt: new Date().toISOString(),
        mode,
        pending: true,
      });
      const controller = new AbortController();
      abortRef.current = controller;
      setIsSending(true);
      setSendingConversationId(conversationId);
      try {
        const history = toHistory(conversation.messages);
        let streamed = "";
        let result: RunForModeResult;
        let statusSetGenerating = false;
        let rafId = 0;
        let pendingFlush = "";
        const flushStream = () => {
          rafId = 0;
          updateMessage(conversationId, assistantId, { content: pendingFlush, pending: true });
        };
        const intent = hasImage
          ? await detectVideoIntent(trimmed, true, controller.signal)
          : { matched: false, intent: null };
        if (intent.matched && readyAttachmentIds.length > 0) {
          setStatus("generating");
          setActiveTool("IMAGE_TO_VIDEO");
          result = await runImageToVideo(trimmed, readyAttachmentIds, controller.signal, (label, content) => {
            updateMessage(conversationId, assistantId, { content, progressLabel: label, pending: true });
          });
        } else if (isBuildProjectIntent(trimmed, Boolean(conversation.buildProjectId))) {
          setStatus("using_tool");
          setActiveTool("BUILD_PROJECT");
          updateMessage(conversationId, assistantId, {
            content: "BUILD_PROJECT · создаю проект…",
            progressLabel: "BUILD_PROJECT",
            pending: true,
          });
          const build = await runBuild(trimmed, {
            conversationId,
            projectId: conversation.buildProjectId,
            signal: controller.signal,
          });
          if (build.project_id) {
            const chat = useChatStore.getState();
            chat.setConversationBuildProjectId(conversationId, build.project_id);
            // Link to existing Projects panel (not a second Artifact engine).
            const title = build.plan?.name || build.slug || "NEXA Build";
            const existing = chat.projects.find(
              (p) => p.instructions.includes(`buildProjectId=${build.project_id}`),
            );
            if (existing) {
              chat.updateProject(existing.id, {
                name: title,
                instructions: `buildProjectId=${build.project_id}\npreview=${build.preview_url || ""}\nstatus=${build.status || ""}`,
                fileNames: build.plan?.files?.length
                  ? build.plan.files
                  : existing.fileNames,
              });
            } else if (build.success) {
              const pid = chat.createProject(title);
              chat.updateProject(pid, {
                instructions: `buildProjectId=${build.project_id}\npreview=${build.preview_url || ""}\nstatus=${build.status || ""}`,
                fileNames: build.plan?.files ?? [],
              });
            }
          }
          const preview = resolveBuildPreviewUrl(build.preview_url);
          const statusNote = build.status ? `\n\nСтатус: \`${build.status}\`` : "";
          const previewNote = preview ? `\n\n[Открыть preview](${preview})` : "";
          result = {
            content:
              (build.message || (build.success ? "Проект готов." : "Сборка не удалась.")) +
              statusNote +
              previewNote,
            modelLabel: build.engine_version === "v2" ? "NEXA · BUILD_PROJECT V2" : "NEXA · BUILD_PROJECT",
            agentSteps: build.steps.map((s, index) => ({
              index,
              stepType: s.status === "failed" ? ("error" as const) : ("tool_call" as const),
              toolName: s.tool ?? s.name,
              toolInput: { detail: s.detail },
              output: s.detail,
              success: s.status !== "failed",
              error: s.status === "failed" ? s.detail : null,
              dryRun: false,
            })),
          };
        } else {
          result = await runForMode(
            mode,
            trimmed,
            history,
            controller.signal,
            readyAttachmentIds,
            (chunk) => {
              streamed += chunk;
              pendingFlush = streamed;
              if (!statusSetGenerating) {
                statusSetGenerating = true;
                setStatus("generating");
              }
              // Batch UI updates to one paint/frame so streaming stays smooth.
              if (!rafId) {
                rafId = window.requestAnimationFrame(flushStream);
              }
            },
          );
          if (rafId) {
            window.cancelAnimationFrame(rafId);
            rafId = 0;
          }
        }
        updateMessage(conversationId, assistantId, {
          content: result.content,
          agentSteps: result.agentSteps,
          modelLabel: result.modelLabel,
          citations: result.citations,
          generatedImages: result.generatedImages,
          generatedVideos: result.generatedVideos,
          progressLabel: undefined,
          pending: false,
          latency: isDebugLatencyEnabled() ? result.latency : undefined,
        });
        setStatus("online");
      } catch (error) {
        if ((error as Error)?.name === "AbortError") {
          updateMessage(conversationId, assistantId, { content: "Stopped.", pending: false });
          setStatus("online");
        } else if (error instanceof ApiError && error.code === "ModelCapabilityError") {
          updateMessage(conversationId, assistantId, { content: "", error: error.message, pending: false });
          setStatus("error");
        } else {
          const message = error instanceof ApiError ? error.message : "Something went wrong talking to NEXA.";
          updateMessage(conversationId, assistantId, { content: "", error: message, pending: false });
          setStatus("error");
        }
      } finally {
        setIsSending(false);
        setSendingConversationId(null);
        setActiveTool(null);
        abortRef.current = null;
      }
    },
    [runForMode, setStatus, setActiveTool],
  );

  const stop = React.useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const retry = React.useCallback(
    (conversationId: string, assistantMessageId: string) => {
      const { conversations, removeMessagesFrom } = useChatStore.getState();
      const conversation = conversations.find((c) => c.id === conversationId);
      if (!conversation) return;
      const idx = conversation.messages.findIndex((m) => m.id === assistantMessageId);
      if (idx === -1) return;
      const priorUser = [...conversation.messages.slice(0, idx)].reverse().find((m) => m.role === "user");
      if (!priorUser) return;
      removeMessagesFrom(conversationId, priorUser.id);
      void send(conversationId, priorUser.content, priorUser.attachments);
    },
    [send],
  );

  const edit = React.useCallback(
    (conversationId: string, userMessageId: string, newContent: string) => {
      const { removeMessagesFrom } = useChatStore.getState();
      removeMessagesFrom(conversationId, userMessageId);
      void send(conversationId, newContent);
    },
    [send],
  );

  return { send, retry, edit, stop, isSending, sendingConversationId };
}
