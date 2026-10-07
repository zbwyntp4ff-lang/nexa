"use client";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { HexaPhase } from "@/lib/hexa/speech";

export interface HexaTurn {
  id: string;
  role: "user" | "assistant";
  content: string;
  at: string;
}

interface HexaState {
  phase: HexaPhase;
  transcript: string;
  interim: string;
  lastReply: string;
  error: string | null;
  voiceId: string | null;
  rate: number;
  pitch: number;
  showKeyboard: boolean;
  history: HexaTurn[];
  energy: number;
  setPhase: (p: HexaPhase) => void;
  setTranscript: (t: string) => void;
  setInterim: (t: string) => void;
  setLastReply: (t: string) => void;
  setError: (e: string | null) => void;
  setVoiceId: (id: string | null) => void;
  setRate: (n: number) => void;
  setPitch: (n: number) => void;
  setShowKeyboard: (v: boolean) => void;
  setEnergy: (n: number) => void;
  pushTurn: (role: HexaTurn["role"], content: string) => void;
  clearHistory: () => void;
}

export const useHexaStore = create<HexaState>()(
  persist(
    (set) => ({
      phase: "idle",
      transcript: "",
      interim: "",
      lastReply: "",
      error: null,
      voiceId: null,
      rate: 1,
      pitch: 1,
      showKeyboard: false,
      history: [],
      energy: 0.2,
      setPhase: (p) => set({ phase: p }),
      setTranscript: (t) => set({ transcript: t }),
      setInterim: (t) => set({ interim: t }),
      setLastReply: (t) => set({ lastReply: t }),
      setError: (e) => set({ error: e }),
      setVoiceId: (id) => set({ voiceId: id }),
      setRate: (n) => set({ rate: n }),
      setPitch: (n) => set({ pitch: n }),
      setShowKeyboard: (v) => set({ showKeyboard: v }),
      setEnergy: (n) => set({ energy: n }),
      pushTurn: (role, content) =>
        set((s) => ({
          history: [
            ...s.history,
            {
              id: `hexa-${Date.now()}-${Math.random().toString(16).slice(2)}`,
              role,
              content,
              at: new Date().toISOString(),
            },
          ].slice(-40),
        })),
      clearHistory: () => set({ history: [] }),
    }),
    {
      name: "nexa-hexa-store",
      partialize: (s) => ({
        voiceId: s.voiceId,
        rate: s.rate,
        pitch: s.pitch,
        history: s.history,
      }),
    }
  )
);
