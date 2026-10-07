import { afterEach, describe, expect, it, vi } from "vitest";
import { getDesktopAppInfo, getDesktopBackendStatus, isDesktopApp, openExternalLink } from "@/lib/electron-bridge";
afterEach(() => {
  delete window.nexa;
});
describe("electron-bridge (browser fallback behavior)", () => {
  it("reports not-desktop when window.nexa is absent", () => {
    expect(isDesktopApp()).toBe(false);
  });
  it("getDesktopAppInfo resolves null outside the desktop app", async () => {
    expect(await getDesktopAppInfo()).toBeNull();
  });
  it("getDesktopBackendStatus resolves null outside the desktop app", async () => {
    expect(await getDesktopBackendStatus()).toBeNull();
  });
  it("openExternalLink falls back to window.open in the browser", () => {
    const spy = vi.spyOn(window, "open").mockImplementation(() => null);
    openExternalLink("https://example.com");
    expect(spy).toHaveBeenCalledWith("https://example.com", "_blank", "noopener,noreferrer");
    spy.mockRestore();
  });
  it("reports desktop and forwards to the bridge when window.nexa is present", async () => {
    const getAppInfo = vi.fn().mockResolvedValue({ version: "1.2.3" });
    const getBackendStatus = vi.fn().mockResolvedValue({ url: "http://127.0.0.1:8420", reachable: true });
    const openExternal = vi.fn().mockResolvedValue(undefined);
    window.nexa = { isDesktop: true, getAppInfo, getBackendStatus, openExternal };
    expect(isDesktopApp()).toBe(true);
    expect(await getDesktopAppInfo()).toEqual({ version: "1.2.3" });
    expect(await getDesktopBackendStatus()).toEqual({ url: "http://127.0.0.1:8420", reachable: true });
    openExternalLink("https://example.com");
    expect(openExternal).toHaveBeenCalledWith("https://example.com");
  });
});
