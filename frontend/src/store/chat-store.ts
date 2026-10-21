"use client";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { AppMode, ChatMessageView, Conversation, Project } from "@/lib/types";

function makeId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function titleFromMessage(text: string): string {
  const trimmed = text.trim().replace(/\s+/g, " ");
  if (!trimmed) return "New chat";
  return trimmed.length > 48 ? `${trimmed.slice(0, 48)}…` : trimmed;
}

type UserChatBucket = {
  conversations: Conversation[];
  activeConversationId: string | null;
  projects: Project[];
};

const emptyBucket = (): UserChatBucket => ({
  conversations: [],
  activeConversationId: null,
  projects: [],
});

interface ChatStoreState extends UserChatBucket {
  /** Active account owning the in-memory chat bucket (null = anonymous/cleared). */
  ownerUserId: string | null;
  /** Per-user local caches — never shown across accounts on the same browser. */
  buckets: Record<string, UserChatBucket>;
  bindUser: (userId: string | null) => void;
  /** Replace active bucket from server (source of truth after login). */
  hydrateFromServer: () => Promise<void>;
  /** Push one conversation to `/conversations` (fire-and-forget safe). */
  pushConversation: (id: string) => Promise<void>;
  createConversation: (mode?: AppMode, projectId?: string | null) => string;
  deleteConversation: (id: string) => void;
  renameConversation: (id: string, title: string) => void;
  setActiveConversation: (id: string | null) => void;
  setConversationMode: (id: string, mode: AppMode) => void;
  setConversationBuildProjectId: (id: string, buildProjectId: string | null) => void;
  addMessage: (conversationId: string, message: ChatMessageView) => void;
  updateMessage: (conversationId: string, messageId: string, patch: Partial<ChatMessageView>) => void;
  removeMessagesFrom: (conversationId: string, messageId: string) => void;
  clearAllChats: () => void;
  createProject: (name: string) => string;
  deleteProject: (id: string) => void;
  updateProject: (id: string, patch: Partial<Project>) => void;
  addFileToProject: (id: string, filename: string) => void;
}

function withBucket(
  state: ChatStoreState,
  patch: Partial<UserChatBucket>,
): Partial<ChatStoreState> {
  const next: UserChatBucket = {
    conversations: patch.conversations ?? state.conversations,
    activeConversationId:
      patch.activeConversationId !== undefined
        ? patch.activeConversationId
        : state.activeConversationId,
    projects: patch.projects ?? state.projects,
  };
  const buckets = { ...state.buckets };
  if (state.ownerUserId) {
    buckets[state.ownerUserId] = next;
  }
  return { ...next, buckets };
}

export const useChatStore = create<ChatStoreState>()(
  persist(
    (set, get) => ({
      ownerUserId: null,
      buckets: {},
      conversations: [],
      activeConversationId: null,
      projects: [],

      bindUser: (userId) => {
        const state = get();
        if (state.ownerUserId === userId) return;
        // Persist current bucket before switching.
        const buckets = { ...state.buckets };
        if (state.ownerUserId) {
          buckets[state.ownerUserId] = {
            conversations: state.conversations,
            activeConversationId: state.activeConversationId,
            projects: state.projects,
          };
        }
        if (!userId) {
          set({
            ownerUserId: null,
            buckets,
            ...emptyBucket(),
          });
          return;
        }
        // Clear UI immediately so the previous account never flashes.
        set({
          ownerUserId: userId,
          buckets,
          conversations: [],
          activeConversationId: null,
          projects: buckets[userId]?.projects ?? [],
        });
      },

      hydrateFromServer: async () => {
        const userId = get().ownerUserId;
        if (!userId) return;
        try {
          const { listServerConversations, toLocalConversation } = await import(
            "@/lib/conversations-api"
          );
          const remote = await listServerConversations();
          const conversations = remote.map(toLocalConversation);
          set((state) =>
            withBucket(state, {
              conversations,
              activeConversationId: conversations[0]?.id ?? null,
            }),
          );
        } catch {
          // Network/auth errors: keep empty server-backed state (no foreign cache).
        }
      },

      pushConversation: async (id) => {
        const state = get();
        if (!state.ownerUserId) return;
        const conversation = state.conversations.find((c) => c.id === id);
        if (!conversation) return;
        try {
          const { upsertServerConversation, toServerMessages } = await import(
            "@/lib/conversations-api"
          );
          const saved = await upsertServerConversation({
            id: conversation.id,
            title: conversation.title,
            mode: conversation.mode,
            messages: toServerMessages(conversation.messages),
          });
          // Keep local id aligned if server returns the same id.
          if (saved.id && saved.id !== conversation.id) {
            set((s) =>
              withBucket(s, {
                conversations: s.conversations.map((c) =>
                  c.id === id ? { ...c, id: saved.id, updatedAt: saved.updated_at } : c,
                ),
                activeConversationId:
                  s.activeConversationId === id ? saved.id : s.activeConversationId,
              }),
            );
          }
        } catch {
          /* offline — local bucket remains until next hydrate */
        }
      },

      createConversation: (mode = "chat", projectId = null) => {
        const id = makeId();
        const now = new Date().toISOString();
        const conversation: Conversation = {
          id,
          title: "New chat",
          mode,
          messages: [],
          projectId,
          createdAt: now,
          updatedAt: now,
        };
        set((state) =>
          withBucket(state, {
            conversations: [conversation, ...state.conversations],
            activeConversationId: id,
          }),
        );
        return id;
      },

      deleteConversation: (id) => {
        const owner = get().ownerUserId;
        set((state) => {
          const conversations = state.conversations.filter((c) => c.id !== id);
          const activeConversationId =
            state.activeConversationId === id
              ? (conversations[0]?.id ?? null)
              : state.activeConversationId;
          return withBucket(state, { conversations, activeConversationId });
        });
        if (owner) {
          void import("@/lib/conversations-api")
            .then(({ deleteServerConversation }) => deleteServerConversation(id))
            .catch(() => undefined);
        }
      },

      renameConversation: (id, title) => {
        set((state) =>
          withBucket(state, {
            conversations: state.conversations.map((c) =>
              c.id === id
                ? { ...c, title: title.trim() || c.title, updatedAt: new Date().toISOString() }
                : c,
            ),
          }),
        );
        if (get().ownerUserId) {
          void get().pushConversation(id);
        }
      },

      setActiveConversation: (id) => {
        set((state) => withBucket(state, { activeConversationId: id }));
      },

      setConversationMode: (id, mode) => {
        set((state) =>
          withBucket(state, {
            conversations: state.conversations.map((c) => (c.id === id ? { ...c, mode } : c)),
          }),
        );
      },

      setConversationBuildProjectId: (id, buildProjectId) => {
        set((state) =>
          withBucket(state, {
            conversations: state.conversations.map((c) =>
              c.id === id ? { ...c, buildProjectId, updatedAt: new Date().toISOString() } : c,
            ),
          }),
        );
      },

      addMessage: (conversationId, message) => {
        set((state) =>
          withBucket(state, {
            conversations: state.conversations.map((c) => {
              if (c.id !== conversationId) return c;
              const messages = [...c.messages, message];
              const isFirstUserMessage = c.title === "New chat" && message.role === "user";
              return {
                ...c,
                messages,
                title: isFirstUserMessage ? titleFromMessage(message.content) : c.title,
                updatedAt: new Date().toISOString(),
              };
            }),
          }),
        );
      },

      updateMessage: (conversationId, messageId, patch) => {
        set((state) =>
          withBucket(state, {
            conversations: state.conversations.map((c) =>
              c.id !== conversationId
                ? c
                : {
                    ...c,
                    messages: c.messages.map((m) => (m.id === messageId ? { ...m, ...patch } : m)),
                    updatedAt: new Date().toISOString(),
                  },
            ),
          }),
        );
      },

      removeMessagesFrom: (conversationId, messageId) => {
        set((state) =>
          withBucket(state, {
            conversations: state.conversations.map((c) => {
              if (c.id !== conversationId) return c;
              const idx = c.messages.findIndex((m) => m.id === messageId);
              if (idx === -1) return c;
              return { ...c, messages: c.messages.slice(0, idx) };
            }),
          }),
        );
      },

      clearAllChats: () => {
        set((state) => withBucket(state, emptyBucket()));
      },

      createProject: (name) => {
        const id = makeId();
        const project: Project = {
          id,
          name: name.trim() || "Untitled project",
          instructions: "",
          fileNames: [],
          createdAt: new Date().toISOString(),
        };
        set((state) => withBucket(state, { projects: [project, ...state.projects] }));
        return id;
      },

      deleteProject: (id) => {
        set((state) =>
          withBucket(state, {
            projects: state.projects.filter((p) => p.id !== id),
            conversations: state.conversations.map((c) =>
              c.projectId === id ? { ...c, projectId: null } : c,
            ),
          }),
        );
      },

      updateProject: (id, patch) => {
        set((state) =>
          withBucket(state, {
            projects: state.projects.map((p) => (p.id === id ? { ...p, ...patch } : p)),
          }),
        );
      },

      addFileToProject: (id, filename) => {
        const project = get().projects.find((p) => p.id === id);
        if (!project) return;
        set((state) =>
          withBucket(state, {
            projects: state.projects.map((p) =>
              p.id === id ? { ...p, fileNames: [...p.fileNames, filename] } : p,
            ),
          }),
        );
      },
    }),
    {
      name: "nexa-chat-store",
      version: 2,
      migrate: (persisted) => {
        const raw = persisted as Partial<ChatStoreState> & UserChatBucket;
        if (raw && raw.buckets) return raw as ChatStoreState;
        // Legacy single-bucket → anonymous orphan (cleared until bindUser).
        return {
          ownerUserId: null,
          buckets: {},
          conversations: [],
          activeConversationId: null,
          projects: [],
        } as ChatStoreState;
      },
    },
  ),
);
