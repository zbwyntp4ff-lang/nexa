/**
 * Static sanity checks for the Electron packaging config and the preload
 * IPC surface (Part 8.5). These don't require an Electron runtime - they
 * just assert the shape of package.json and the preload script's source.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
const electronDir = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const packageJson = JSON.parse(fs.readFileSync(path.join(electronDir, "..", "package.json"), "utf8"));
const preloadSource = fs.readFileSync(path.join(electronDir, "preload.js"), "utf8");
const mainSource = fs.readFileSync(path.join(electronDir, "main.js"), "utf8");
describe("electron-builder packaging config", () => {
  it("names the app NEXA and points main at electron/main.js", () => {
    expect(packageJson.main).toBe("electron/main.js");
    expect(packageJson.build.productName).toBe("NEXA");
  });
  it("configures a Windows installer and a portable build", () => {
    expect(packageJson.build.win.target).toEqual(["nsis", "portable"]);
    expect(packageJson.build.win.icon).toBe("build/icon.ico");
  });
  it("does not bundle a foreign-platform Python venv into the Windows target", () => {
    const winExtra = JSON.stringify(packageJson.build.win.extraResources || []);
    expect(winExtra).not.toContain(".venv");
  });
});
describe("preload IPC surface", () => {
  it("uses contextBridge with a fixed whitelist, never a generic invoke passthrough", () => {
    expect(preloadSource).toContain("contextBridge.exposeInMainWorld");
    expect(preloadSource).not.toMatch(/invoke:\s*ipcRenderer\.invoke\s*,?\s*$/m);
    expect(preloadSource).not.toContain("ipcRenderer.invoke(channel"); // no pass-any-channel helper
  });
  it("validates openExternal only accepts http(s) URLs before touching IPC", () => {
    expect(preloadSource).toMatch(/ALLOWED_EXTERNAL_URL/);
  });
});
describe("main process security posture", () => {
  it("disables nodeIntegration and enables contextIsolation + sandbox", () => {
    expect(mainSource).toMatch(/nodeIntegration:\s*false/);
    expect(mainSource).toMatch(/contextIsolation:\s*true/);
    expect(mainSource).toMatch(/sandbox:\s*true/);
  });
  it("sets a Content-Security-Policy header", () => {
    expect(mainSource).toContain("Content-Security-Policy");
  });
  it("only stops a backend process it spawned itself, and only spawns one when none is reachable", () => {
    const backendSource = fs.readFileSync(path.join(__dirname, "..", "backend.js"), "utf8");
    expect(backendSource).toContain("spawnedByUs");
    expect(backendSource).toContain("already reachable");
  });
});
