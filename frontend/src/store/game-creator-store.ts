"use client";
import { create } from "zustand";

export type GameCreatorTab = "preview" | "code" | "scene" | "console" | "assets" | "export";

export interface GameConsoleLine {
  id: string;
  at: number;
  level: "info" | "warn" | "error" | "event";
  text: string;
}

interface GameCreatorState {
  open: boolean;
  projectId: string | null;
  previewUrl: string | null;
  title: string;
  files: string[];
  stack: string | null;
  tab: GameCreatorTab;
  selectedFile: string | null;
  fileContent: string;
  sceneJson: string | null;
  consoleLines: GameConsoleLine[];
  previewRunning: boolean;
  previewKey: number;
  openGameCreator: (opts: {
    projectId: string;
    previewUrl: string | null;
    title?: string;
    files?: string[];
    stack?: string | null;
  }) => void;
  closeGameCreator: () => void;
  setTab: (tab: GameCreatorTab) => void;
  setSelectedFile: (file: string | null) => void;
  setFileContent: (content: string) => void;
  setSceneJson: (json: string | null) => void;
  setFiles: (files: string[]) => void;
  pushConsole: (level: GameConsoleLine["level"], text: string) => void;
  clearConsole: () => void;
  runPreview: () => void;
  stopPreview: () => void;
  restartPreview: () => void;
}

let lineSeq = 0;

export const useGameCreatorStore = create<GameCreatorState>((set, get) => ({
  open: false,
  projectId: null,
  previewUrl: null,
  title: "Game Creator",
  files: [],
  stack: null,
  tab: "preview",
  selectedFile: null,
  fileContent: "",
  sceneJson: null,
  consoleLines: [],
  previewRunning: true,
  previewKey: 0,
  openGameCreator: ({ projectId, previewUrl, title, files, stack }) =>
    set({
      open: true,
      projectId,
      previewUrl,
      title: title || "Game Creator",
      files: files ?? [],
      stack: stack ?? null,
      tab: "preview",
      selectedFile: files?.[0] ?? "main.js",
      fileContent: "",
      sceneJson: null,
      consoleLines: [
        {
          id: `c-${++lineSeq}`,
          at: Date.now(),
          level: "info",
          text: `Opened project ${projectId}`,
        },
      ],
      previewRunning: true,
      previewKey: get().previewKey + 1,
    }),
  closeGameCreator: () =>
    set({
      open: false,
      previewRunning: false,
      previewUrl: null,
    }),
  setTab: (tab) => set({ tab }),
  setSelectedFile: (file) => set({ selectedFile: file }),
  setFileContent: (content) => set({ fileContent: content }),
  setSceneJson: (json) => set({ sceneJson: json }),
  setFiles: (files) => set({ files }),
  pushConsole: (level, text) =>
    set((s) => ({
      consoleLines: [
        ...s.consoleLines.slice(-199),
        { id: `c-${++lineSeq}`, at: Date.now(), level, text },
      ],
    })),
  clearConsole: () => set({ consoleLines: [] }),
  runPreview: () =>
    set((s) => ({
      previewRunning: true,
      previewKey: s.previewKey + 1,
    })),
  stopPreview: () => set({ previewRunning: false }),
  restartPreview: () =>
    set((s) => ({
      previewRunning: true,
      previewKey: s.previewKey + 1,
    })),
}));

export function isThreeBuild(input: {
  stack?: string | null;
  files?: string[] | null;
  message?: string | null;
}): boolean {
  if (input.files?.includes("scene.json")) return true;
  if (input.stack && /three\.?js/i.test(input.stack)) return true;
  if (input.message && /(3\s*d|three\.?js|webgl|трёхмер|трехмер|гонк|racing|flight|танк|tank|приключ|adventure)/i.test(input.message)) {
    return true;
  }
  return false;
}
