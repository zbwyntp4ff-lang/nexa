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
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  BackendManager,
  probeBackend,
  resolveBackendCwd,
  resolvePythonExecutable,
  resolveDesktopStorageEnv,
  migrateLegacyData,
  DEFAULT_BACKEND_URL,
  normalizeLoopbackBackendUrl,
} from "../backend.js";
describe("resolveBackendCwd", () => {
  it("resolves the repo root two levels above electron/ in dev mode", () => {
    const electronDir = "/workspace/frontend/electron";
    const cwd = resolveBackendCwd({ isPackaged: false, electronDir });
    expect(cwd).toBe(path.join(electronDir, "..", ".."));
  });
  it("uses localhost as the default backend host for cookie same-site consistency", () => {
    expect(DEFAULT_BACKEND_URL).toBe("http://localhost:8420");
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

  it("sends a termination signal only to the backend process it spawned", () => {
    const manager = new BackendManager({ url: "http://127.0.0.1:8420", electronDir: __dirname });
    const kill = vi.fn();
    manager.process = { killed: false, kill };
    manager.spawnedByUs = true;

    manager.stop();

    expect(kill).toHaveBeenCalledTimes(1);
    expect(manager.process).toBeNull();
  });
  it("does not send duplicate termination signals after stop", () => {
    const manager = new BackendManager({ url: "http://127.0.0.1:8420", electronDir: __dirname });
    const kill = vi.fn();
    manager.process = { killed: false, kill };
    manager.spawnedByUs = true;

    manager.stop();
    manager.stop();

    expect(kill).toHaveBeenCalledTimes(1);
    expect(manager.process).toBeNull();
  });
  it("never kills a backend it did not spawn", () => {
    const manager = new BackendManager({ url: "http://127.0.0.1:1", electronDir: __dirname });
    manager.process = { killed: false, kill: () => { throw new Error("must not be called"); } };
    manager.spawnedByUs = false;
    expect(() => manager.stop()).not.toThrow();
  });
});


describe("resolveDesktopStorageEnv", () => {
  it("places writable desktop stores beneath the per-user data directory", () => {
    const userData = path.join(os.tmpdir(), "nexa-user-data");
    const env = resolveDesktopStorageEnv(userData, {});
    const dataDir = path.join(userData, "data");
    expect(env.AUTH_STORE_PATH).toBe(path.join(dataDir, "auth_store.json"));
    expect(env.PLUGIN_STORE_PATH).toBe(path.join(dataDir, "plugin_store.json"));
    expect(env.PLUGIN_KEY_PATH).toBe(path.join(dataDir, "plugin.key"));
    expect(env.MEMORY_STORE_PATH).toBe(path.join(dataDir, "memory_store.json"));
    expect(env.AGENT_WORKSPACE_DIR).toBe(path.join(dataDir, "agent_workspace"));
    expect(env.ATTACHMENT_STORAGE_DIR).toBe(path.join(dataDir, "attachments_tmp"));
    expect(env.VIDEO_STORAGE_DIR).toBe(path.join(dataDir, "videos"));
    expect(env.OAUTH_CREDENTIALS_DIR).toBe(path.join(dataDir, "oauth"));
    expect(env.DATABASE_URL).toBe(`sqlite:///${path.join(dataDir, "nexa.db").replace(/\\/g, "/")}`);
  });

  it("preserves an explicitly configured external database URL", () => {
    const url = "postgresql://db.example/nexa";
    expect(resolveDesktopStorageEnv("/tmp/nexa-user", { DATABASE_URL: url }).DATABASE_URL).toBe(url);
  });
});


describe("migrateLegacyData", () => {
  it("moves legacy stores and workspaces only when the userData copy is missing", () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "nexa-legacy-"));
    const userData = fs.mkdtempSync(path.join(os.tmpdir(), "nexa-user-"));
    const legacyData = path.join(root, "data");
    fs.mkdirSync(legacyData, { recursive: true });
    fs.writeFileSync(path.join(legacyData, "auth_store.json"), "legacy-auth");
    fs.writeFileSync(path.join(legacyData, "plugin.key"), "legacy-key");
    fs.mkdirSync(path.join(legacyData, "videos"), { recursive: true });
    fs.writeFileSync(path.join(legacyData, "videos", "clip.mp4"), "video");
    fs.mkdirSync(path.join(root, "agent_workspace"), { recursive: true });
    fs.writeFileSync(path.join(root, "agent_workspace", "note.txt"), "workspace");

    const targetData = path.join(userData, "data");
    fs.mkdirSync(targetData, { recursive: true });
    fs.writeFileSync(path.join(targetData, "auth_store.json"), "newer-auth");
    const messages = [];
    migrateLegacyData({ legacyRoot: root, userDataDir: userData, onLog: (message) => messages.push(message) });

    expect(fs.readFileSync(path.join(targetData, "auth_store.json"), "utf8")).toBe("newer-auth");
    expect(fs.readFileSync(path.join(targetData, "plugin.key"), "utf8")).toBe("legacy-key");
    expect(fs.readFileSync(path.join(targetData, "videos", "clip.mp4"), "utf8")).toBe("video");
    expect(fs.readFileSync(path.join(targetData, "agent_workspace", "note.txt"), "utf8")).toBe("workspace");
    expect(messages).toContain("Migrated desktop data: data/plugin.key");
  });
});


describe("normalizeLoopbackBackendUrl", () => {
  it("maps IPv4 loopback to localhost for browser cookie consistency", () => {
    expect(normalizeLoopbackBackendUrl("http://127.0.0.1:8420")).toBe("http://localhost:8420");
  });
  it("leaves non-loopback and HTTPS backend URLs unchanged", () => {
    expect(normalizeLoopbackBackendUrl("https://api.example.com")).toBe("https://api.example.com");
    expect(normalizeLoopbackBackendUrl("http://192.168.1.5:8420")).toBe("http://192.168.1.5:8420");
  });
});
