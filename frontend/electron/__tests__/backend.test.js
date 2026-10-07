/**
 * Tests for the Electron backend-lifecycle helper (Part 8.5).
 *
 * No real Electron runtime is needed here - `backend.js` deliberately has
 * no dependency on the `electron` module, only Node built-ins, so these
 * run under plain Vitest.
 */
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  BackendManager,
  probeBackend,
  resolveBackendCwd,
  resolvePythonExecutable,
} from "../backend.js";
describe("resolveBackendCwd", () => {
  it("resolves the repo root two levels above electron/ in dev mode", () => {
    const electronDir = "/workspace/frontend/electron";
    const cwd = resolveBackendCwd({ isPackaged: false, electronDir });
    expect(cwd).toBe(path.join(electronDir, "..", ".."));
  });
  it("resolves resourcesPath/backend when packaged", () => {
    const cwd = resolveBackendCwd({ isPackaged: true, resourcesPath: "/opt/NEXA/resources" });
    expect(cwd).toBe(path.join("/opt/NEXA/resources", "backend"));
  });
});
describe("resolvePythonExecutable", () => {
  let tmpDir;
  afterEach(() => {
    if (tmpDir) fs.rmSync(tmpDir, { recursive: true, force: true });
    tmpDir = undefined;
  });
  it("falls back to the system python3 when no bundled venv exists", () => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "nexa-backend-"));
    expect(resolvePythonExecutable(tmpDir, "linux")).toBe("python3");
    expect(resolvePythonExecutable(tmpDir, "win32")).toBe("python");
  });
  it("prefers a bundled venv python when present for the current platform", () => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "nexa-backend-"));
    const venvBin = path.join(tmpDir, ".venv", "bin");
    fs.mkdirSync(venvBin, { recursive: true });
    const venvPython = path.join(venvBin, "python3");
    fs.writeFileSync(venvPython, "#!/bin/sh\n");
    expect(resolvePythonExecutable(tmpDir, "linux")).toBe(venvPython);
  });
});
describe("probeBackend", () => {
  it("resolves true when the health endpoint answers 200", async () => {
    const server = http.createServer((req, res) => {
      if (req.url === "/health") {
        res.writeHead(200);
        res.end("ok");
      } else {
        res.writeHead(404);
        res.end();
      }
    });
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    const port = server.address().port;
    try {
      expect(await probeBackend(`http://127.0.0.1:${port}`)).toBe(true);
    } finally {
      server.close();
    }
  });
  it("resolves false when nothing is listening", async () => {
    // Port 1 is a privileged/unassigned port unlikely to have a listener.
    expect(await probeBackend("http://127.0.0.1:1", 300)).toBe(false);
  });
});
describe("BackendManager", () => {
  it("reuses an already-running backend instead of spawning a duplicate", async () => {
    const server = http.createServer((req, res) => {
      res.writeHead(200);
      res.end("ok");
    });
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    const port = server.address().port;
    try {
      const logs = [];
      const manager = new BackendManager({
        url: `http://127.0.0.1:${port}`,
        isPackaged: false,
        electronDir: __dirname,
        onLog: (line) => logs.push(line),
      });
      const healthy = await manager.ensureRunning();
      expect(healthy).toBe(true);
      expect(manager.spawnedByUs).toBe(false);
      expect(logs.some((l) => l.includes("already reachable"))).toBe(true);
    } finally {
      server.close();
    }
  });
  it("never kills a backend it did not spawn", () => {
    const manager = new BackendManager({ url: "http://127.0.0.1:1", electronDir: __dirname });
    manager.process = { killed: false, kill: () => { throw new Error("must not be called"); } };
    manager.spawnedByUs = false;
    expect(() => manager.stop()).not.toThrow();
  });
});
