import { afterEach, describe, expect, it, vi } from "vitest";
import {
  beginSpeakGeneration,
  currentSpeakGeneration,
  extractSpeakableChunks,
  normalizeSttLang,
  stopSpeaking,
} from "@/lib/hexa/speech";

describe("hexa speech helpers", () => {
  afterEach(() => {
    stopSpeaking();
    vi.unstubAllGlobals();
  });

  it("normalizeSttLang maps ru/en", () => {
    expect(normalizeSttLang("ru")).toBe("ru-RU");
    expect(normalizeSttLang("ru-RU")).toBe("ru-RU");
    expect(normalizeSttLang("en-US")).toBe("en-US");
    expect(normalizeSttLang("")).toBe("en-US");
  });

  it("extractSpeakableChunks splits on sentence boundaries", () => {
    const { chunks, rest } = extractSpeakableChunks("Hello world. Next part");
    expect(chunks).toEqual(["Hello world."]);
    expect(rest).toBe("Next part");
  });

  it("extractSpeakableChunks keeps incomplete sentence in rest", () => {
    const { chunks, rest } = extractSpeakableChunks("Still talking without end");
    expect(chunks).toEqual([]);
    expect(rest).toContain("Still talking");
  });

  it("stopSpeaking bumps generation so stale TTS is ignored", () => {
    const before = beginSpeakGeneration();
    stopSpeaking();
    expect(currentSpeakGeneration()).toBeGreaterThan(before);
  });
});
