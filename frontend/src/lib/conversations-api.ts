import { request } from "@/lib/api";
import type { AppMode, ChatMessageView, Conversation } from "@/lib/types";

export interface ConversationApi {
  id: string;
  title: string;
  mode: string;
  messages: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
}

export function listServerConversations(signal?: AbortSignal) {
  return request<ConversationApi[]>("/api/v1/conversations?limit=100", { signal });
}

export function getServerConversation(id: string, signal?: AbortSignal) {
  return request<ConversationApi>(`/api/v1/conversations/${encodeURIComponent(id)}`, {
    signal,
  });
}

export function upsertServerConversation(
  body: {
    id?: string;
    title: string;
    mode: string;
    messages: Array<Record<string, unknown>>;
  },
  signal?: AbortSignal,
) {
  return request<ConversationApi>("/api/v1/conversations", {
    method: "PUT",
    body: JSON.stringify(body),
    signal,
  });
}

export function deleteServerConversation(id: string, signal?: AbortSignal) {
  return request<{ deleted: boolean; id: string }>(
    `/api/v1/conversations/${encodeURIComponent(id)}`,
    { method: "DELETE", signal },
  );
}

/** Map server conversation → local Chat store shape. Server is source of truth. */
export function toLocalConversation(api: ConversationApi): Conversation {
  const messages: ChatMessageView[] = (api.messages || []).map((m, index) => ({
    id: String(m.id ?? `srv-${api.id}-${index}`),
    role: (m.role as ChatMessageView["role"]) || "assistant",
    content: String(m.content ?? ""),
    createdAt: String(m.createdAt ?? m.created_at ?? api.updated_at),
    mode: (api.mode as AppMode) || "chat",
    pending: Boolean(m.pending),
    error: m.error ? String(m.error) : undefined,
    modelLabel: m.modelLabel ? String(m.modelLabel) : undefined,
  }));
  return {
    id: api.id,
    title: api.title || "New chat",
    mode: (api.mode as AppMode) || "chat",
    messages,
    projectId: null,
    createdAt: api.created_at,
    updatedAt: api.updated_at,
  };
}

export function toServerMessages(messages: ChatMessageView[]) {
  return messages
    .filter((m) => !m.pending)
    .map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      createdAt: m.createdAt,
      mode: m.mode,
      modelLabel: m.modelLabel,
      error: m.error,
    }));
}
