/** Browser speech helpers for HEXA voice chat. */

export type HexaPhase = "idle" | "listening" | "thinking" | "speaking" | "typing";

export interface HexaVoiceOption {
  id: string;
  name: string;
  lang: string;
  localService: boolean;
}

type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((ev: SpeechRecognitionEventLike) => void) | null;
  onerror: ((ev: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};

type SpeechRecognitionEventLike = {
  resultIndex: number;
  results: ArrayLike<{ 0: { transcript: string }; isFinal: boolean; length: number }>;
};

function getRecognitionCtor(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === "undefined") return null;
  const w = window as Window & {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function speechRecognitionSupported(): boolean {
  return Boolean(getRecognitionCtor());
}

export function speechSynthesisSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export function listVoices(): HexaVoiceOption[] {
  if (!speechSynthesisSupported()) return [];
  return window.speechSynthesis.getVoices().map((v) => ({
    id: `${v.name}::${v.lang}`,
    name: v.name,
    lang: v.lang,
    localService: v.localService,
  }));
}

export function findVoice(voiceId: string | null): SpeechSynthesisVoice | null {
  if (!speechSynthesisSupported() || !voiceId) return null;
  return window.speechSynthesis.getVoices().find((v) => `${v.name}::${v.lang}` === voiceId) ?? null;
}

export function createRecognition(lang: string): SpeechRecognitionLike | null {
  const Ctor = getRecognitionCtor();
  if (!Ctor) return null;
  const rec = new Ctor();
  rec.lang = lang;
  rec.continuous = false;
  rec.interimResults = true;
  rec.maxAlternatives = 1;
  return rec;
}

export function speakText(
  text: string,
  opts: {
    voiceId: string | null;
    rate?: number;
    pitch?: number;
    onStart?: () => void;
    onEnd?: () => void;
    onBoundary?: () => void;
  }
): void {
  if (!speechSynthesisSupported()) {
    opts.onEnd?.();
    return;
  }
  window.speechSynthesis.cancel();
  const utter = new SpeechSynthesisUtterance(text);
  const voice = findVoice(opts.voiceId);
  if (voice) utter.voice = voice;
  utter.rate = opts.rate ?? 1;
  utter.pitch = opts.pitch ?? 1;
  utter.onstart = () => opts.onStart?.();
  utter.onend = () => opts.onEnd?.();
  utter.onerror = () => opts.onEnd?.();
  utter.onboundary = () => opts.onBoundary?.();
  window.speechSynthesis.speak(utter);
}

export function stopSpeaking(): void {
  if (speechSynthesisSupported()) window.speechSynthesis.cancel();
}
