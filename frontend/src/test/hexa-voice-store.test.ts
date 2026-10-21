import { beforeEach, describe, expect, it } from "vitest";
import { useHexaStore } from "@/store/hexa-store";

describe("hexa store voice prefs", () => {
  beforeEach(() => {
    useHexaStore.setState({
      continuousMode: true,
      autoSpeak: true,
      sttLang: "en-US",
      sttLangInitialized: false,
      micMuted: false,
      sessionArmed: false,
      phase: "idle",
      error: null,
    });
  });

  it("seeds STT lang from UI once", () => {
    useHexaStore.getState().seedSttLangFromUi("ru");
    expect(useHexaStore.getState().sttLang).toBe("ru-RU");
    expect(useHexaStore.getState().sttLangInitialized).toBe(true);
    useHexaStore.getState().seedSttLangFromUi("en");
    expect(useHexaStore.getState().sttLang).toBe("ru-RU");
  });

  it("mute is session-only flag", () => {
    useHexaStore.getState().setMicMuted(true);
    expect(useHexaStore.getState().micMuted).toBe(true);
  });

  it("setSttLang marks initialized", () => {
    useHexaStore.getState().setSttLang("en-US");
    expect(useHexaStore.getState().sttLangInitialized).toBe(true);
  });
});
