"use client";
import * as React from "react";
import { sendChat, type ChatApiMessage } from "@/lib/api";
import {
  createRecognition,
  listVoices,
  speakText,
  speechRecognitionSupported,
  speechSynthesisSupported,
  stopSpeaking,
  type HexaVoiceOption,
} from "@/lib/hexa/speech";
import { useHexaStore } from "@/store/hexa-store";
import { useI18nStore } from "@/lib/i18n-store";

export function useHexaVoice() {
  const language = useI18nStore((s) => s.language);
  const phase = useHexaStore((s) => s.phase);
  const voiceId = useHexaStore((s) => s.voiceId);
  const rate = useHexaStore((s) => s.rate);
  const pitch = useHexaStore((s) => s.pitch);
  const history = useHexaStore((s) => s.history);
  const setPhase = useHexaStore((s) => s.setPhase);
  const setTranscript = useHexaStore((s) => s.setTranscript);
  const setInterim = useHexaStore((s) => s.setInterim);
  const setLastReply = useHexaStore((s) => s.setLastReply);
  const setError = useHexaStore((s) => s.setError);
  const setVoiceId = useHexaStore((s) => s.setVoiceId);
  const setEnergy = useHexaStore((s) => s.setEnergy);
  const pushTurn = useHexaStore((s) => s.pushTurn);

  const [voices, setVoices] = React.useState<HexaVoiceOption[]>([]);
  const recRef = React.useRef<ReturnType<typeof createRecognition>>(null);
  const abortRef = React.useRef<AbortController | null>(null);
  const energyTimer = React.useRef<number | null>(null);

  const sttLang = language === "ru" ? "ru-RU" : "en-US";

  React.useEffect(() => {
    const refresh = () => {
      const list = listVoices();
      setVoices(list);
      if (!useHexaStore.getState().voiceId && list.length) {
        const preferred =
          list.find((v) => v.lang.toLowerCase().startsWith(language === "ru" ? "ru" : "en")) ?? list[0];
        setVoiceId(preferred.id);
      }
    };
    refresh();
    if (speechSynthesisSupported()) {
      window.speechSynthesis.onvoiceschanged = refresh;
      return () => {
        window.speechSynthesis.onvoiceschanged = null;
      };
    }
  }, [language, setVoiceId]);

  React.useEffect(() => {
    return () => {
      stopListening();
      stopSpeaking();
      abortRef.current?.abort();
      if (energyTimer.current) window.clearInterval(energyTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function pulseEnergy(mode: "listen" | "speak" | "think" | "idle") {
    if (energyTimer.current) window.clearInterval(energyTimer.current);
    if (mode === "idle") {
      setEnergy(0.15);
      return;
    }
    energyTimer.current = window.setInterval(() => {
      const base = mode === "speak" ? 0.55 : mode === "listen" ? 0.35 : 0.25;
      const jitter = Math.random() * (mode === "speak" ? 0.45 : 0.25);
      setEnergy(Math.min(1, base + jitter));
    }, mode === "speak" ? 90 : 140);
  }

  function stopListening() {
    try {
      recRef.current?.abort();
    } catch {
      /* ignore */
    }
    recRef.current = null;
  }

  async function askNexa(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;
    stopListening();
    stopSpeaking();
    setError(null);
    setTranscript(trimmed);
    setInterim("");
    pushTurn("user", trimmed);
    setPhase("thinking");
    pulseEnergy("think");

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const apiHistory: ChatApiMessage[] = useHexaStore
      .getState()
      .history.filter((t) => t.role === "user" || t.role === "assistant")
      .slice(0, -1)
      .map((t) => ({ role: t.role, content: t.content }));

    try {
      const response = await sendChat(trimmed, apiHistory, controller.signal, {
        task: "chat",
      });
      const reply = (response.message || "").trim() || (language === "ru" ? "Готово." : "Done.");
      setLastReply(reply);
      pushTurn("assistant", reply);
      setPhase("speaking");
      pulseEnergy("speak");
      speakText(reply, {
        voiceId: useHexaStore.getState().voiceId,
        rate: useHexaStore.getState().rate,
        pitch: useHexaStore.getState().pitch,
        onStart: () => {
          setPhase("speaking");
          pulseEnergy("speak");
        },
        onBoundary: () => setEnergy(0.4 + Math.random() * 0.6),
        onEnd: () => {
          setPhase("idle");
          pulseEnergy("idle");
        },
      });
    } catch (err) {
      if ((err as Error)?.name === "AbortError") return;
      const msg =
        language === "ru"
          ? "Не удалось получить ответ. Проверьте backend и попробуйте ещё раз."
          : "Couldn't get a reply. Check the backend and try again.";
      setError(msg);
      setLastReply(msg);
      setPhase("speaking");
      pulseEnergy("speak");
      speakText(msg, {
        voiceId: useHexaStore.getState().voiceId,
        rate: useHexaStore.getState().rate,
        pitch: useHexaStore.getState().pitch,
        onEnd: () => {
          setPhase("idle");
          pulseEnergy("idle");
        },
      });
    }
  }

  function startListening() {
    if (!speechRecognitionSupported()) {
      setError(
        language === "ru"
          ? "Распознавание речи не поддерживается в этом окружении. Используйте клавиатуру."
          : "Speech recognition isn't supported here. Use the keyboard."
      );
      useHexaStore.getState().setShowKeyboard(true);
      return;
    }
    stopSpeaking();
    stopListening();
    setError(null);
    setInterim("");
    const rec = createRecognition(sttLang);
    if (!rec) return;
    recRef.current = rec;
    setPhase("listening");
    pulseEnergy("listen");

    rec.onresult = (ev) => {
      let interim = "";
      let finalText = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const piece = ev.results[i][0]?.transcript ?? "";
        if (ev.results[i].isFinal) finalText += piece;
        else interim += piece;
      }
      if (interim) setInterim(interim);
      if (finalText.trim()) {
        setInterim("");
        void askNexa(finalText);
      }
    };
    rec.onerror = (ev) => {
      if (ev.error === "aborted" || ev.error === "no-speech") {
        setPhase("idle");
        pulseEnergy("idle");
        return;
      }
      setError(
        language === "ru"
          ? `Ошибка распознавания: ${ev.error}`
          : `Recognition error: ${ev.error}`
      );
      setPhase("idle");
      pulseEnergy("idle");
    };
    rec.onend = () => {
      if (useHexaStore.getState().phase === "listening") {
        setPhase("idle");
        pulseEnergy("idle");
      }
    };
    try {
      rec.start();
    } catch {
      setError(language === "ru" ? "Не удалось запустить микрофон." : "Couldn't start the microphone.");
      setPhase("idle");
      pulseEnergy("idle");
    }
  }

  function toggleMic() {
    if (phase === "listening") {
      stopListening();
      setPhase("idle");
      pulseEnergy("idle");
      return;
    }
    if (phase === "speaking" || phase === "thinking") {
      abortRef.current?.abort();
      stopSpeaking();
      setPhase("idle");
      pulseEnergy("idle");
      return;
    }
    startListening();
  }

  function stopAll() {
    abortRef.current?.abort();
    stopListening();
    stopSpeaking();
    setPhase("idle");
    pulseEnergy("idle");
  }

  return {
    phase,
    voices,
    voiceId,
    setVoiceId,
    rate,
    pitch,
    history,
    sttSupported: speechRecognitionSupported(),
    ttsSupported: speechSynthesisSupported(),
    toggleMic,
    startListening,
    askNexa,
    stopAll,
  };
}
