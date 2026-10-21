/** Browser speech helpers for HEXA voice chat (Part 12). */

export type HexaPhase =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "typing"
  | "interrupted"
  | "error";

export type SttLang = "ru-RU" | "en-US";

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

export function normalizeSttLang(value: string | null | undefined): SttLang {
  const v = (value || "").trim().toLowerCase();
  if (v.startsWith("ru")) return "ru-RU";
  return "en-US";
}

/** Split streamed assistant text into speakable sentence chunks. */
export function extractSpeakableChunks(buffer: string): { chunks: string[]; rest: string } {
  const chunks: string[] = [];
  let rest = buffer;
  // Prefer sentence boundaries; fall back to long clause breaks.
  const re = /[.!?…]+(?:["»”')\]]+)?(?:\s+|$)|(?:\n{2,})/g;
  let match: RegExpExecArray | null;
  let lastIndex = 0;
  while ((match = re.exec(buffer)) !== null) {
    const end = match.index + match[0].length;
    const piece = buffer.slice(lastIndex, end).trim();
    if (piece) chunks.push(piece);
    lastIndex = end;
  }
  rest = buffer.slice(lastIndex);
  // If rest is very long without punctuation, flush a soft chunk at whitespace.
  if (rest.length > 220) {
    const cut = rest.lastIndexOf(" ", 180);
    if (cut > 40) {
      chunks.push(rest.slice(0, cut).trim());
      rest = rest.slice(cut).trimStart();
    }
  }
  return { chunks, rest };
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

export function createRecognition(
  lang: string,
  opts?: { continuous?: boolean },
): SpeechRecognitionLike | null {
  const Ctor = getRecognitionCtor();
  if (!Ctor) return null;
  const rec = new Ctor();
  rec.lang = normalizeSttLang(lang);
  rec.continuous = Boolean(opts?.continuous);
  rec.interimResults = true;
  rec.maxAlternatives = 1;
  return rec;
}

let speakGeneration = 0;
let speakQueue: string[] = [];
let speakBusy = false;
let speakOpts: {
  voiceId: string | null;
  lang?: string;
  rate?: number;
  pitch?: number;
  generation: number;
  onStart?: () => void;
  onEnd?: () => void;
  onBoundary?: () => void;
} | null = null;

export function currentSpeakGeneration(): number {
  return speakGeneration;
}

function pumpSpeakQueue(): void {
  if (speakBusy || !speakOpts) return;
  const next = speakQueue.shift();
  if (!next) {
    const opts = speakOpts;
    speakOpts = null;
    opts.onEnd?.();
    return;
  }
  if (!speechSynthesisSupported()) {
    speakOpts.onEnd?.();
    speakOpts = null;
    speakQueue = [];
    return;
  }
  const opts = speakOpts;
  const generation = opts.generation;
  speakBusy = true;
  const utter = new SpeechSynthesisUtterance(next);
  const voice = findVoice(opts.voiceId);
  if (voice) {
    utter.voice = voice;
    utter.lang = voice.lang || opts.lang || "en-US";
  } else if (opts.lang) {
    utter.lang = opts.lang;
  }
  utter.rate = opts.rate ?? 1;
  utter.pitch = opts.pitch ?? 1;
  utter.onstart = () => {
    if (generation !== speakGeneration) return;
    opts.onStart?.();
  };
  utter.onboundary = () => {
    if (generation !== speakGeneration) return;
    opts.onBoundary?.();
  };
  const finish = () => {
    if (generation !== speakGeneration) {
      speakBusy = false;
      return;
    }
    speakBusy = false;
    pumpSpeakQueue();
  };
  utter.onend = finish;
  utter.onerror = finish;
  window.speechSynthesis.speak(utter);
}

export function speakText(
  text: string,
  opts: {
    voiceId: string | null;
    lang?: string;
    rate?: number;
    pitch?: number;
    generation?: number;
    onStart?: () => void;
    onEnd?: () => void;
    onBoundary?: () => void;
  },
): number {
  const generation = opts.generation ?? ++speakGeneration;
  speakGeneration = generation;
  speakQueue = [];
  speakBusy = false;
  if (speechSynthesisSupported()) window.speechSynthesis.cancel();
  const trimmed = text.trim();
  if (!trimmed) {
    opts.onEnd?.();
    return generation;
  }
  speakOpts = {
    voiceId: opts.voiceId,
    lang: opts.lang,
    rate: opts.rate,
    pitch: opts.pitch,
    generation,
    onStart: opts.onStart,
    onEnd: opts.onEnd,
    onBoundary: opts.onBoundary,
  };
  speakQueue = [trimmed];
  pumpSpeakQueue();
  return generation;
}

/** Enqueue speakable fragments for the active generation (streaming TTS). */
export function enqueueSpeakChunks(
  chunks: string[],
  opts: {
    voiceId: string | null;
    lang?: string;
    rate?: number;
    pitch?: number;
    generation: number;
    onStart?: () => void;
    onEnd?: () => void;
    onBoundary?: () => void;
  },
): void {
  if (opts.generation !== speakGeneration) return;
  const cleaned = chunks.map((c) => c.trim()).filter(Boolean);
  if (!cleaned.length) return;
  if (!speakOpts || speakOpts.generation !== opts.generation) {
    speakOpts = {
      voiceId: opts.voiceId,
      lang: opts.lang,
      rate: opts.rate,
      pitch: opts.pitch,
      generation: opts.generation,
      onStart: opts.onStart,
      onEnd: opts.onEnd,
      onBoundary: opts.onBoundary,
    };
  }
  speakQueue.push(...cleaned);
  pumpSpeakQueue();
}

export function finishSpeakQueue(generation: number, remainder?: string): void {
  if (generation !== speakGeneration || !speakOpts) {
    if (remainder?.trim() && generation === speakGeneration) {
      enqueueSpeakChunks([remainder], {
        voiceId: null,
        generation,
      });
    }
    return;
  }
  if (remainder?.trim()) speakQueue.push(remainder.trim());
  // Mark that after queue drains, onEnd fires (already wired).
  if (!speakBusy && speakQueue.length === 0) {
    const opts = speakOpts;
    speakOpts = null;
    opts.onEnd?.();
  } else {
    pumpSpeakQueue();
  }
}

export function stopSpeaking(): void {
  speakGeneration += 1;
  speakQueue = [];
  speakBusy = false;
  speakOpts = null;
  if (speechSynthesisSupported()) window.speechSynthesis.cancel();
}

export function beginSpeakGeneration(): number {
  stopSpeaking();
  speakGeneration += 1;
  return speakGeneration;
}
