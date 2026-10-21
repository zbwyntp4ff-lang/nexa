"use client";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import { normalizeSttLang, type HexaPhase, type SttLang } from "@/lib/hexa/speech";

export interface HexaTurn {
  id: string;
  role: "user" | "assistant";
  content: string;
  at: string;
}

export interface HexaTiming {
  recognitionMs?: number;
  requestMs?: number;
  ttftMs?: number;
  fullReplyMs?: number;
  ttsStartMs?: number;
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
  continuousMode: boolean;
  autoSpeak: boolean;
  sttLang: SttLang;
  sttLangInitialized: boolean;
  micMuted: boolean;
  sessionArmed: boolean;
  lastTiming: HexaTiming | null;
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
  setContinuousMode: (v: boolean) => void;
  setAutoSpeak: (v: boolean) => void;
  setSttLang: (lang: SttLang) => void;
  setMicMuted: (v: boolean) => void;
  setSessionArmed: (v: boolean) => void;
  setLastTiming: (t: HexaTiming | null) => void;
  seedSttLangFromUi: (uiLang: "en" | "ru") => void;
  pushTurn: (role: HexaTurn["role"], content: string) => void;
  clearHistory: () => void;
}

export const useHexaStore = create<HexaState>()(
  persist(
    (set, get) => ({
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
      continuousMode: true,
      autoSpeak: true,
      sttLang: "en-US",
      sttLangInitialized: false,
      micMuted: false,
      sessionArmed: false,
      lastTiming: null,
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
      setContinuousMode: (v) => set({ continuousMode: v }),
      setAutoSpeak: (v) => set({ autoSpeak: v }),
      setSttLang: (lang) => set({ sttLang: normalizeSttLang(lang), sttLangInitialized: true }),
      setMicMuted: (v) => set({ micMuted: v }),
      setSessionArmed: (v) => set({ sessionArmed: v }),
      setLastTiming: (t) => set({ lastTiming: t }),
      seedSttLangFromUi: (uiLang) => {
        if (get().sttLangInitialized) return;
        set({
          sttLang: uiLang === "ru" ? "ru-RU" : "en-US",
          sttLangInitialized: true,
        });
      },
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
        continuousMode: s.continuousMode,
        autoSpeak: s.autoSpeak,
        sttLang: s.sttLang,
        sttLangInitialized: s.sttLangInitialized,
      }),
    },
  ),
);
