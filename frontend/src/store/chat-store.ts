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
interface ChatStoreState {
  conversations: Conversation[];
  activeConversationId: string | null;
  projects: Project[];
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
export const useChatStore = create<ChatStoreState>()(
  persist(
    (set, get) => ({
      conversations: [],
      activeConversationId: null,
      projects: [],
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
        set((state) => ({
          conversations: [conversation, ...state.conversations],
          activeConversationId: id,
        }));
        return id;
      },
      deleteConversation: (id) => {
        set((state) => {
          const conversations = state.conversations.filter((c) => c.id !== id);
          const activeConversationId =
            state.activeConversationId === id ? (conversations[0]?.id ?? null) : state.activeConversationId;
          return { conversations, activeConversationId };
        });
      },
      renameConversation: (id, title) => {
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === id ? { ...c, title: title.trim() || c.title, updatedAt: new Date().toISOString() } : c
          ),
        }));
      },
      setActiveConversation: (id) => set({ activeConversationId: id }),
      setConversationMode: (id, mode) => {
        set((state) => ({
          conversations: state.conversations.map((c) => (c.id === id ? { ...c, mode } : c)),
        }));
      },
      setConversationBuildProjectId: (id, buildProjectId) => {
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === id ? { ...c, buildProjectId, updatedAt: new Date().toISOString() } : c,
          ),
        }));
      },
      addMessage: (conversationId, message) => {
        set((state) => ({
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
        }));
      },
      updateMessage: (conversationId, messageId, patch) => {
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id !== conversationId
              ? c
              : {
                  ...c,
                  messages: c.messages.map((m) => (m.id === messageId ? { ...m, ...patch } : m)),
                  updatedAt: new Date().toISOString(),
                }
          ),
        }));
      },
      removeMessagesFrom: (conversationId, messageId) => {
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c;
            const idx = c.messages.findIndex((m) => m.id === messageId);
            if (idx === -1) return c;
            return { ...c, messages: c.messages.slice(0, idx) };
          }),
        }));
      },
      clearAllChats: () => set({ conversations: [], activeConversationId: null }),
      createProject: (name) => {
        const id = makeId();
        const project: Project = {
          id,
          name: name.trim() || "Untitled project",
          instructions: "",
          fileNames: [],
          createdAt: new Date().toISOString(),
        };
        set((state) => ({ projects: [project, ...state.projects] }));
        return id;
      },
      deleteProject: (id) => {
        set((state) => ({
          projects: state.projects.filter((p) => p.id !== id),
          conversations: state.conversations.map((c) =>
            c.projectId === id ? { ...c, projectId: null } : c
          ),
        }));
      },
      updateProject: (id, patch) => {
        set((state) => ({
          projects: state.projects.map((p) => (p.id === id ? { ...p, ...patch } : p)),
        }));
      },
      addFileToProject: (id, filename) => {
        const project = get().projects.find((p) => p.id === id);
        if (!project) return;
        set((state) => ({
          projects: state.projects.map((p) =>
            p.id === id ? { ...p, fileNames: [...p.fileNames, filename] } : p
          ),
        }));
      },
    }),
    { name: "nexa-chat-store" }
  )
);
