"use client";
import * as React from "react";
import { sendChat, type ChatApiMessage } from "@/lib/api";
import {
  beginSpeakGeneration,
  createRecognition,
  enqueueSpeakChunks,
  extractSpeakableChunks,
  finishSpeakQueue,
  listVoices,
  normalizeSttLang,
  speakText,
  speechRecognitionSupported,
  speechSynthesisSupported,
  stopSpeaking,
  type HexaVoiceOption,
} from "@/lib/hexa/speech";
import { useHexaStore } from "@/store/hexa-store";
import { useI18nStore } from "@/lib/i18n-store";

const UTTERANCE_SILENCE_MS = 900;

export function useHexaVoice() {
  const language = useI18nStore((s) => s.language);
  const phase = useHexaStore((s) => s.phase);
  const voiceId = useHexaStore((s) => s.voiceId);
  const rate = useHexaStore((s) => s.rate);
  const pitch = useHexaStore((s) => s.pitch);
  const history = useHexaStore((s) => s.history);
  const continuousMode = useHexaStore((s) => s.continuousMode);
  const autoSpeak = useHexaStore((s) => s.autoSpeak);
  const sttLang = useHexaStore((s) => s.sttLang);
  const micMuted = useHexaStore((s) => s.micMuted);
  const setPhase = useHexaStore((s) => s.setPhase);
  const setTranscript = useHexaStore((s) => s.setTranscript);
  const setInterim = useHexaStore((s) => s.setInterim);
  const setLastReply = useHexaStore((s) => s.setLastReply);
  const setError = useHexaStore((s) => s.setError);
  const setVoiceId = useHexaStore((s) => s.setVoiceId);
  const setEnergy = useHexaStore((s) => s.setEnergy);
  const pushTurn = useHexaStore((s) => s.pushTurn);
  const setSessionArmed = useHexaStore((s) => s.setSessionArmed);
  const setLastTiming = useHexaStore((s) => s.setLastTiming);
  const seedSttLangFromUi = useHexaStore((s) => s.seedSttLangFromUi);

  const [voices, setVoices] = React.useState<HexaVoiceOption[]>([]);
  const recRef = React.useRef<ReturnType<typeof createRecognition>>(null);
  const abortRef = React.useRef<AbortController | null>(null);
  const energyTimer = React.useRef<number | null>(null);
  const askingRef = React.useRef(false);
  const silenceTimer = React.useRef<number | null>(null);
  const pendingFinal = React.useRef("");
  const listenStartedAt = React.useRef<number>(0);
  const speakGenRef = React.useRef(0);
  const wantListenAfterSpeak = React.useRef(false);

  React.useEffect(() => {
    seedSttLangFromUi(language);
  }, [language, seedSttLangFromUi]);

  React.useEffect(() => {
    const refresh = () => {
      const list = listVoices();
      setVoices(list);
      if (!useHexaStore.getState().voiceId && list.length) {
        const pref = normalizeSttLang(useHexaStore.getState().sttLang).slice(0, 2);
        const preferred = list.find((v) => v.lang.toLowerCase().startsWith(pref)) ?? list[0];
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
  }, [sttLang, setVoiceId]);

  React.useEffect(() => {
    return () => {
      clearSilenceTimer();
      stopListening();
      stopSpeaking();
      abortRef.current?.abort();
      if (energyTimer.current) window.clearInterval(energyTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function clearSilenceTimer() {
    if (silenceTimer.current) {
      window.clearTimeout(silenceTimer.current);
      silenceTimer.current = null;
    }
  }

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
    clearSilenceTimer();
    pendingFinal.current = "";
    try {
      recRef.current?.abort();
    } catch {
      /* ignore */
    }
    recRef.current = null;
  }

  function maybeContinueListening() {
    const s = useHexaStore.getState();
    if (!s.continuousMode || s.micMuted || !s.sessionArmed) {
      setPhase("idle");
      pulseEnergy("idle");
      return;
    }
    startListening({ fromAuto: true });
  }

  function interrupt(reason: "stop" | "barge" = "stop") {
    abortRef.current?.abort();
    abortRef.current = null;
    askingRef.current = false;
    wantListenAfterSpeak.current = false;
    stopSpeaking();
    speakGenRef.current = beginSpeakGeneration();
    stopListening();
    setPhase("interrupted");
    pulseEnergy("idle");
    window.setTimeout(() => {
      if (useHexaStore.getState().phase !== "interrupted") return;
      if (reason === "barge" || (useHexaStore.getState().continuousMode && !useHexaStore.getState().micMuted)) {
        maybeContinueListening();
      } else {
        setPhase("idle");
      }
    }, 280);
  }

  async function askNexa(text: string) {
    const trimmed = text.trim();
    if (!trimmed || askingRef.current) return;
    askingRef.current = true;
    clearSilenceTimer();
    pendingFinal.current = "";
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

    const recognitionMs = listenStartedAt.current
      ? Math.max(0, performance.now() - listenStartedAt.current)
      : undefined;
    const requestStarted = performance.now();
    let firstTokenAt: number | null = null;
    let ttsStartedAt: number | null = null;

    const apiHistory: ChatApiMessage[] = useHexaStore
      .getState()
      .history.filter((t) => t.role === "user" || t.role === "assistant")
      .slice(0, -1)
      .map((t) => ({ role: t.role, content: t.content }));

    const generation = beginSpeakGeneration();
    speakGenRef.current = generation;
    let streamBuffer = "";
    let spokenRest = "";
    const doAutoSpeak = useHexaStore.getState().autoSpeak;

    const ttsLang = normalizeSttLang(useHexaStore.getState().sttLang);
    const speakCommon = {
      voiceId: useHexaStore.getState().voiceId,
      lang: ttsLang,
      rate: useHexaStore.getState().rate,
      pitch: useHexaStore.getState().pitch,
      generation,
      onStart: () => {
        if (speakGenRef.current !== generation) return;
        if (ttsStartedAt == null) ttsStartedAt = performance.now();
        setPhase("speaking");
        pulseEnergy("speak");
      },
      onBoundary: () => setEnergy(0.4 + Math.random() * 0.6),
      onEnd: () => {
        if (speakGenRef.current !== generation) return;
        askingRef.current = false;
        if (wantListenAfterSpeak.current || useHexaStore.getState().continuousMode) {
          wantListenAfterSpeak.current = false;
          maybeContinueListening();
        } else {
          setPhase("idle");
          pulseEnergy("idle");
        }
      },
    };

    try {
      const response = await sendChat(trimmed, apiHistory, controller.signal, {
        task: "chat",
        onFirstToken: () => {
          firstTokenAt = performance.now();
        },
        onDelta: (chunk) => {
          if (controller.signal.aborted || speakGenRef.current !== generation) return;
          streamBuffer += chunk;
          if (!doAutoSpeak) return;
          spokenRest += chunk;
          const { chunks, rest } = extractSpeakableChunks(spokenRest);
          spokenRest = rest;
          if (chunks.length) {
            if (useHexaStore.getState().phase === "thinking") {
              setPhase("speaking");
              pulseEnergy("speak");
            }
            enqueueSpeakChunks(chunks, speakCommon);
          }
        },
      });
      if (controller.signal.aborted || speakGenRef.current !== generation) {
        askingRef.current = false;
        return;
      }
      const reply =
        (response.message || streamBuffer || "").trim() ||
        (language === "ru" ? "Готово." : "Done.");
      setLastReply(reply);
      pushTurn("assistant", reply);
      const fullReplyMs = performance.now() - requestStarted;
      setLastTiming({
        recognitionMs,
        requestMs: fullReplyMs,
        ttftMs: firstTokenAt != null ? firstTokenAt - requestStarted : undefined,
        fullReplyMs,
        ttsStartMs: ttsStartedAt != null ? ttsStartedAt - requestStarted : undefined,
      });

      if (!doAutoSpeak) {
        askingRef.current = false;
        setPhase("idle");
        pulseEnergy("idle");
        if (useHexaStore.getState().continuousMode) maybeContinueListening();
        return;
      }

      const leftover = spokenRest.trim() || (!streamBuffer ? reply : "");
      spokenRest = "";
      if (leftover) {
        setPhase("speaking");
        pulseEnergy("speak");
        enqueueSpeakChunks([leftover], speakCommon);
      }
      finishSpeakQueue(generation);
      if (!speechSynthesisSupported()) {
        askingRef.current = false;
        speakCommon.onEnd?.();
      }
    } catch (err) {
      askingRef.current = false;
      if ((err as Error)?.name === "AbortError") return;
      const msg =
        language === "ru"
          ? "Не удалось получить ответ. Проверьте backend и попробуйте ещё раз."
          : "Couldn't get a reply. Check the backend and try again.";
      setError(msg);
      setLastReply(msg);
      setPhase("error");
      if (doAutoSpeak) {
        speakText(msg, {
          ...speakCommon,
          generation: beginSpeakGeneration(),
          onEnd: () => {
            setPhase("idle");
            pulseEnergy("idle");
            if (useHexaStore.getState().continuousMode) maybeContinueListening();
          },
        });
      } else {
        pulseEnergy("idle");
      }
    }
  }

  function scheduleAskFromFinal(piece: string) {
    pendingFinal.current = `${pendingFinal.current} ${piece}`.trim();
    clearSilenceTimer();
    silenceTimer.current = window.setTimeout(() => {
      const text = pendingFinal.current.trim();
      pendingFinal.current = "";
      if (text) void askNexa(text);
    }, UTTERANCE_SILENCE_MS);
  }

  function startListening(opts?: { fromAuto?: boolean }) {
    if (useHexaStore.getState().micMuted) {
      setPhase("idle");
      pulseEnergy("idle");
      return;
    }
    if (!speechRecognitionSupported()) {
      setError(
        language === "ru"
          ? "Распознавание речи не поддерживается в этом окружении. Используйте клавиатуру."
          : "Speech recognition isn't supported here. Use the keyboard.",
      );
      useHexaStore.getState().setShowKeyboard(true);
      setPhase("error");
      return;
    }
    // Explicit user arming — auto-continue only after sessionArmed
    if (!opts?.fromAuto) {
      setSessionArmed(true);
    } else if (!useHexaStore.getState().sessionArmed) {
      return;
    }

    stopSpeaking();
    stopListening();
    setError(null);
    setInterim("");
    listenStartedAt.current = performance.now();
    const continuous = useHexaStore.getState().continuousMode;
    const rec = createRecognition(useHexaStore.getState().sttLang, { continuous });
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
        scheduleAskFromFinal(finalText);
      }
    };
    rec.onerror = (ev) => {
      if (ev.error === "aborted" || ev.error === "no-speech") {
        if (useHexaStore.getState().phase === "listening") {
          setPhase("idle");
          pulseEnergy("idle");
        }
        return;
      }
      setError(
        language === "ru" ? `Ошибка распознавания: ${ev.error}` : `Recognition error: ${ev.error}`,
      );
      setPhase("error");
      pulseEnergy("idle");
    };
    rec.onend = () => {
      // Continuous mode: restart recognition while still listening
      if (
        useHexaStore.getState().phase === "listening" &&
        useHexaStore.getState().continuousMode &&
        !useHexaStore.getState().micMuted &&
        recRef.current === rec
      ) {
        try {
          rec.start();
          return;
        } catch {
          /* fall through */
        }
      }
      if (pendingFinal.current.trim() && !askingRef.current) {
        const text = pendingFinal.current.trim();
        pendingFinal.current = "";
        void askNexa(text);
        return;
      }
      if (useHexaStore.getState().phase === "listening") {
        setPhase("idle");
        pulseEnergy("idle");
      }
    };
    try {
      rec.start();
    } catch {
      setError(language === "ru" ? "Не удалось запустить микрофон." : "Couldn't start the microphone.");
      setPhase("error");
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
      interrupt("barge");
      return;
    }
    startListening();
  }

  function stopAll() {
    setSessionArmed(false);
    wantListenAfterSpeak.current = false;
    interrupt("stop");
    setPhase("idle");
    pulseEnergy("idle");
  }

  function stopSpeakingOnly() {
    if (phase === "speaking" || phase === "thinking") {
      interrupt("stop");
    } else {
      stopSpeaking();
    }
  }

  function toggleMute() {
    const next = !useHexaStore.getState().micMuted;
    useHexaStore.getState().setMicMuted(next);
    if (next) {
      stopListening();
      if (phase === "listening") {
        setPhase("idle");
        pulseEnergy("idle");
      }
    } else if (
      useHexaStore.getState().continuousMode &&
      useHexaStore.getState().sessionArmed &&
      phase === "idle"
    ) {
      startListening({ fromAuto: true });
    }
  }

  function replayLast() {
    const reply = useHexaStore.getState().lastReply;
    if (!reply.trim()) return;
    stopListening();
    const generation = beginSpeakGeneration();
    speakGenRef.current = generation;
    setPhase("speaking");
    pulseEnergy("speak");
    speakText(reply, {
      voiceId: useHexaStore.getState().voiceId,
      lang: normalizeSttLang(useHexaStore.getState().sttLang),
      rate: useHexaStore.getState().rate,
      pitch: useHexaStore.getState().pitch,
      generation,
      onStart: () => {
        setPhase("speaking");
        pulseEnergy("speak");
      },
      onEnd: () => {
        setPhase("idle");
        pulseEnergy("idle");
      },
    });
  }

  return {
    phase,
    voices,
    voiceId,
    setVoiceId,
    rate,
    pitch,
    history,
    continuousMode,
    autoSpeak,
    sttLang,
    micMuted,
    sttSupported: speechRecognitionSupported(),
    ttsSupported: speechSynthesisSupported(),
    toggleMic,
    startListening,
    askNexa,
    stopAll,
    stopSpeakingOnly,
    toggleMute,
    replayLast,
    interrupt,
  };
}
