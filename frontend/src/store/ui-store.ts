"use client";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { AppMode, AppStatus } from "@/lib/types";
export type AppView = "chat" | "omniverse" | "hexa";
export type SettingsSection =
  | "general"
  | "appearance"
  | "models"
  | "memory"
  | "knowledge"
  | "learning"
  | "privacy"
  | "tools"
  | "plugins"
  | "billing"
  | "tokens"
  | "personalization"
  | "about";
interface UiStoreState {
  activeView: AppView;
  setActiveView: (view: AppView) => void;
  mobileDrawerOpen: boolean;
  setMobileDrawerOpen: (open: boolean) => void;
  desktopSidebarCollapsed: boolean;
  toggleDesktopSidebar: () => void;
  settingsOpen: boolean;
  settingsSection: SettingsSection;
  openSettings: (section?: SettingsSection) => void;
  closeSettings: () => void;
  projectsOpen: boolean;
  activeProjectId: string | null;
  openProjects: (projectId?: string | null) => void;
  closeProjects: () => void;
  workflowsOpen: boolean;
  openWorkflows: () => void;
  closeWorkflows: () => void;
  status: AppStatus;
  setStatus: (status: AppStatus) => void;
  activeTool: string | null;
  setActiveTool: (tool: string | null) => void;
  /** Mode selected before a conversation exists yet (applied when one is created). */
  pendingMode: AppMode;
  setPendingMode: (mode: AppMode) => void;
  /** Bumped when switching modes so the chat panel can animate a fresh tab. */
  panelMotionKey: number;
  bumpPanelMotion: () => void;
}
export const useUiStore = create<UiStoreState>()(
  persist(
    (set) => ({
      activeView: "chat",
      setActiveView: (view) => set({ activeView: view }),
      mobileDrawerOpen: false,
      setMobileDrawerOpen: (open) => set({ mobileDrawerOpen: open }),
      desktopSidebarCollapsed: false,
      toggleDesktopSidebar: () =>
        set((state) => ({ desktopSidebarCollapsed: !state.desktopSidebarCollapsed })),
      settingsOpen: false,
      settingsSection: "general",
      openSettings: (section = "general") => set({ settingsOpen: true, settingsSection: section }),
      closeSettings: () => set({ settingsOpen: false }),
      projectsOpen: false,
      activeProjectId: null,
      openProjects: (projectId = null) => set({ projectsOpen: true, activeProjectId: projectId }),
      closeProjects: () => set({ projectsOpen: false }),
      workflowsOpen: false,
      openWorkflows: () => set({ workflowsOpen: true }),
      closeWorkflows: () => set({ workflowsOpen: false }),
      status: "offline",
      setStatus: (status) => set({ status }),
      activeTool: null,
      setActiveTool: (tool) => set({ activeTool: tool }),
      pendingMode: "chat",
      setPendingMode: (mode) => set({ pendingMode: mode }),
      panelMotionKey: 0,
      bumpPanelMotion: () => set((state) => ({ panelMotionKey: state.panelMotionKey + 1 })),
    }),
    {
      name: "nexa-ui-store",
      version: 2,
      migrate: (persisted) => {
        const state = (persisted ?? {}) as Partial<UiStoreState>;
        return {
          desktopSidebarCollapsed: Boolean(state.desktopSidebarCollapsed),
          // Drop any stored omniverse/hexa view from older builds.
          activeView: "chat" as const,
        };
      },
      partialize: (state) => ({
        desktopSidebarCollapsed: state.desktopSidebarCollapsed,
        // Do not persist activeView — omniverse/hexa crashes used to reopen
        // into a broken session and show Chromium's "couldn't load" page.
      }),
    }
  )
);
