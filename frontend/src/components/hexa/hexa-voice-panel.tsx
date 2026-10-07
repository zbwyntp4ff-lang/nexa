"use client";
import * as React from "react";
import { Crosshair, Keyboard, Menu, Mic, X } from "lucide-react";
import { HexaHistory } from "@/components/hexa/hexa-history";
import { HexaOrb } from "@/components/hexa/hexa-orb";
import { useHexaVoice } from "@/hooks/use-hexa-voice";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { useHexaStore } from "@/store/hexa-store";
import { useUiStore } from "@/store/ui-store";

export function HexaVoicePanel() {
  const t = useT();
  const setActiveView = useUiStore((s) => s.setActiveView);
  const openSettings = useUiStore((s) => s.openSettings);
  const energy = useHexaStore((s) => s.energy);
  const interim = useHexaStore((s) => s.interim);
  const transcript = useHexaStore((s) => s.transcript);
  const lastReply = useHexaStore((s) => s.lastReply);
  const error = useHexaStore((s) => s.error);
  const showKeyboard = useHexaStore((s) => s.showKeyboard);
  const setShowKeyboard = useHexaStore((s) => s.setShowKeyboard);
  const rate = useHexaStore((s) => s.rate);
  const pitch = useHexaStore((s) => s.pitch);
  const setRate = useHexaStore((s) => s.setRate);
  const setPitch = useHexaStore((s) => s.setPitch);
  const [draft, setDraft] = React.useState("");
  const [voicesOpen, setVoicesOpen] = React.useState(false);

  const { phase, voices, voiceId, setVoiceId, toggleMic, askNexa, stopAll, sttSupported, ttsSupported } =
    useHexaVoice();

  const title =
    phase === "listening"
      ? t("hexa.listening")
      : phase === "thinking"
        ? t("hexa.thinking")
        : phase === "speaking"
          ? t("hexa.speaking")
          : phase === "typing"
            ? t("hexa.typing")
            : t("hexa.ready");

  const subtitle =
    phase === "listening"
      ? t("hexa.listeningHint")
      : phase === "speaking"
        ? lastReply.slice(0, 120) || t("hexa.speakingHint")
        : phase === "thinking"
          ? t("hexa.thinkingHint")
          : interim || transcript || t("hexa.readyHint");

  return (
    <div className="hexa-screen relative flex h-full min-h-0 flex-col bg-black text-white">
      <header className="flex items-center justify-between px-5 pt-3 pb-1">
        <button
          type="button"
          aria-label={t("hexa.menu")}
          onClick={() => openSettings()}
          className="rounded-full p-2 text-white/90 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
        >
          <Menu className="size-6" />
        </button>
        <h1 className="text-sm font-medium tracking-[0.35em] text-white">HEXA</h1>
        <button
          type="button"
          aria-label={t("hexa.voices")}
          onClick={() => setVoicesOpen((v) => !v)}
          className="rounded-full p-2 text-white/90 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
        >
          <Crosshair className="size-5" />
        </button>
      </header>

      {voicesOpen && (
        <div className="absolute top-16 right-4 z-20 w-[min(20rem,calc(100%-2rem))] rounded-2xl border border-white/10 bg-[#12121a]/95 p-3 shadow-2xl backdrop-blur-xl">
          <p className="mb-2 text-[11px] font-semibold tracking-wider text-white/50 uppercase">{t("hexa.voices")}</p>
          {!ttsSupported && <p className="text-xs text-rose-300">{t("hexa.ttsUnsupported")}</p>}
          <div className="max-h-48 space-y-1 overflow-y-auto nexa-scrollbar">
            {voices.map((v) => (
              <button
                key={v.id}
                type="button"
                onClick={() => setVoiceId(v.id)}
                className={cn(
                  "flex w-full flex-col rounded-lg px-2.5 py-2 text-left text-xs hover:bg-white/10",
                  voiceId === v.id && "bg-white/15"
                )}
              >
                <span className="font-medium">{v.name}</span>
                <span className="text-white/45">{v.lang}</span>
              </button>
            ))}
            {voices.length === 0 && <p className="text-xs text-white/50">{t("hexa.noVoices")}</p>}
          </div>
          <label className="mt-3 flex items-center justify-between gap-2 text-[11px] text-white/60">
            {t("hexa.rate")}
            <input
              type="range"
              min={0.7}
              max={1.4}
              step={0.05}
              value={rate}
              onChange={(e) => setRate(Number(e.target.value))}
              className="w-28"
            />
          </label>
          <label className="mt-2 flex items-center justify-between gap-2 text-[11px] text-white/60">
            {t("hexa.pitch")}
            <input
              type="range"
              min={0.7}
              max={1.4}
              step={0.05}
              value={pitch}
              onChange={(e) => setPitch(Number(e.target.value))}
              className="w-28"
            />
          </label>
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 px-4 pb-1 md:grid-cols-[minmax(12rem,16rem)_minmax(0,1fr)] md:items-center md:gap-4 md:px-5 lg:grid-cols-[minmax(13rem,17rem)_minmax(0,1fr)_minmax(13rem,17rem)]">
        <div className="hidden max-h-[72%] min-h-0 self-center md:block">
          <HexaHistory />
        </div>

        <div className="flex min-h-0 flex-col items-center justify-center gap-5 px-2">
          <HexaOrb phase={phase} energy={energy} />
          <div className="max-w-md space-y-1.5 text-center">
            <p className="text-2xl font-semibold tracking-tight">{title}</p>
            <p className="text-sm text-white/55">{subtitle}</p>
            {error && <p className="text-sm text-rose-300">{error}</p>}
            {!sttSupported && <p className="text-xs text-amber-200/80">{t("hexa.sttUnsupported")}</p>}
          </div>
        </div>

        <div className="hidden lg:block" aria-hidden />
      </div>

      <div className="mx-4 mb-2 h-28 min-h-0 md:hidden">
        <HexaHistory />
      </div>

      {showKeyboard && (
        <form
          className="mx-auto mb-3 flex w-full max-w-lg gap-2 px-5"
          onSubmit={(e) => {
            e.preventDefault();
            const text = draft.trim();
            if (!text) return;
            setDraft("");
            void askNexa(text);
          }}
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={t("hexa.typePlaceholder")}
            className="h-11 flex-1 rounded-full border border-white/15 bg-white/5 px-4 text-sm text-white outline-none placeholder:text-white/35 focus:border-white/35"
            autoFocus
          />
          <button
            type="submit"
            className="rounded-full bg-white/10 px-4 text-sm font-medium hover:bg-white/15"
          >
            {t("hexa.send")}
          </button>
        </form>
      )}

      <div className="flex items-center justify-center gap-8 pb-6 pt-1">
        <button
          type="button"
          aria-label={t("hexa.keyboard")}
          onClick={() => setShowKeyboard(!showKeyboard)}
          className="flex size-12 items-center justify-center rounded-full bg-[#2a2a32] text-white hover:bg-[#34343e] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
        >
          <Keyboard className="size-5" />
        </button>
        <button
          type="button"
          aria-label={t("hexa.mic")}
          onClick={toggleMic}
          className={cn(
            "hexa-mic-btn flex size-[4.5rem] items-center justify-center rounded-full text-white shadow-[0_0_40px_rgba(120,80,255,0.45)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50",
            phase === "listening" && "hexa-mic-active"
          )}
        >
          <Mic className="size-7" />
        </button>
        <button
          type="button"
          aria-label={t("hexa.close")}
          onClick={() => {
            stopAll();
            setActiveView("chat");
          }}
          className="flex size-12 items-center justify-center rounded-full bg-[#2a2a32] text-white hover:bg-[#34343e] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
        >
          <X className="size-5" />
        </button>
      </div>
    </div>
  );
}
