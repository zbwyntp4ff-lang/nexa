/**
 * Backend lifecycle helper for the NEXA desktop shell (Part 8.5).
 *
 * Deliberately has no dependency on the `electron` module so its pure
 * logic (path resolution, health probing) can be unit-tested with plain
 * Node/Vitest. `main.js` wires this into app lifecycle events.
 *
 * Design:
 *  - Never spawns a second backend if one is already answering on the
 *    configured URL (dev workflows that already run uvicorn manually keep
 *    working unchanged).
 *  - Only ever stops a backend process *this* module started - an
 *    externally-started backend is left running on quit.
 *  - stdout/stderr from the backend are piped into the desktop log file
 *    as-is; the backend's own `SecretRedactionFilter` (app/core/logging_config.py)
 *    already scrubs API keys before they reach stdout, so nothing here
 *    needs to re-implement that redaction.
 */
"use strict";
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { spawn } = require("node:child_process");
const DEFAULT_BACKEND_URL = "http://localhost:8420";
const HEALTH_PATH = "/health";
const MAX_STARTUP_WAIT_MS = 20_000;
const STARTUP_POLL_INTERVAL_MS = 300;
function probeBackend(baseUrl, timeoutMs = 1500) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (ok) => {
      if (settled) return;
      settled = true;
      resolve(ok);
    };
    try {
      const req = http.get(`${baseUrl}${HEALTH_PATH}`, { timeout: timeoutMs }, (res) => {
        finish(res.statusCode === 200);
        res.resume();
      });
      req.on("error", () => finish(false));
      req.on("timeout", () => {
        req.destroy();
        finish(false);
      });
    } catch {
      finish(false);
    }
  });
}
/** Resolve the repo/backend working directory for dev vs. packaged mode. */
function normalizeLoopbackBackendUrl(url) {
  const parsed = new URL(String(url));
  if (parsed.protocol === "http:" && ["127.0.0.1", "::1"].includes(parsed.hostname)) {
    parsed.hostname = "localhost";
  }
  const pathname = parsed.pathname === "/" ? "" : parsed.pathname.replace(/\/$/, "");
  return `${parsed.protocol}//${parsed.host}${pathname}${parsed.search}${parsed.hash}`;
}
function resolveBackendCwd({ isPackaged, resourcesPath, electronDir }) {
  if (isPackaged) {
    return path.join(resourcesPath, "backend");
  }
  // electron/backend.js -> electron -> frontend -> <repo root>
  return path.join(electronDir, "..", "..");
}
/** Find a Python executable able to run the backend: prefer a bundled venv
 * for the current platform, then fall back to a system `python3`/`python`. */
function resolvePythonExecutable(backendCwd, platform = process.platform) {
  const venvPython =
    platform === "win32"
      ? path.join(backendCwd, ".venv", "Scripts", "python.exe")
      : path.join(backendCwd, ".venv", "bin", "python3");
  if (fs.existsSync(venvPython)) {
    return venvPython;
  }
  return platform === "win32" ? "python" : "python3";
}
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
const LEGACY_DATA_MIGRATIONS = [
  ["data/nexa.db", "nexa.db"],
  ["data/auth_store.json", "auth_store.json"],
  ["data/memory_store.json", "memory_store.json"],
  ["agent_workspace", "agent_workspace"],
  ["data/plugin_store.json", "plugin_store.json"],
  ["data/plugin_workspaces", "plugin_workspaces"],
  ["data/plugin.key", "plugin.key"],
  ["data/attachments_tmp", "attachments_tmp"],
  ["data/knowledge_vectors.json", "knowledge_vectors.json"],
  ["data/knowledge_documents.json", "knowledge_documents.json"],
  ["data/videos", "videos"],
  ["data/oauth", "oauth"],
  ["data/billing_store.json", "billing_store.json"],
  ["data/token_store.json", "token_store.json"],
  ["data/profile_store.json", "profile_store.json"],
];

/** Migrate legacy writable data out of read-only packaged resources once. */
function migrateLegacyData({ legacyRoot, userDataDir, onLog = () => {} }) {
  const dataDir = path.join(userDataDir, "data");
  fs.mkdirSync(dataDir, { recursive: true, mode: 0o700 });
  try {
    fs.chmodSync(dataDir, 0o700);
  } catch {
    // Windows ACLs are inherited from the per-user Electron data directory.
  }

  for (const [legacyRelative, targetRelative] of LEGACY_DATA_MIGRATIONS) {
    const source = path.join(legacyRoot, legacyRelative);
    const target = path.join(dataDir, targetRelative);
    if (fs.existsSync(target) || !fs.existsSync(source)) continue;

    const sourceStat = fs.lstatSync(source);
    if (sourceStat.isSymbolicLink()) {
      onLog(`Skipped symlink during desktop data migration: ${legacyRelative}`);
      continue;
    }

    const parent = path.dirname(target);
    fs.mkdirSync(parent, { recursive: true, mode: 0o700 });
    const temp = `${target}.migration-${process.pid}-${Date.now()}`;
    try {
      if (sourceStat.isDirectory()) {
        fs.cpSync(source, temp, {
          recursive: true,
          filter: (candidate) => {
            try {
              return !fs.lstatSync(candidate).isSymbolicLink();
            } catch {
              return false;
            }
          },
        });
      } else if (sourceStat.isFile()) {
        fs.copyFileSync(source, temp, fs.constants.COPYFILE_EXCL);
      } else {
        continue;
      }
      if (fs.existsSync(target)) {
        fs.rmSync(temp, { recursive: true, force: true });
        continue;
      }
      fs.renameSync(temp, target);
      onLog(`Migrated desktop data: ${legacyRelative}`);
    } catch (error) {
      fs.rmSync(temp, { recursive: true, force: true });
      throw error;
    }
  }
  return dataDir;
}
/**
 * Place every writable desktop store under Electron's per-user data directory.
 * Packaged app resources are read-only on macOS and Windows.
 */
function resolveDesktopStorageEnv(userDataDir, env = process.env) {
  const dataDir = path.join(userDataDir, "data");
  const dataFile = (name) => path.join(dataDir, name);
  const sqlitePath = dataFile("nexa.db").replace(/\\/g, "/");
  return {
    DATABASE_URL: env.DATABASE_URL || `sqlite:///${sqlitePath}`,
    AUTH_STORE_PATH: dataFile("auth_store.json"),
    MEMORY_STORE_PATH: dataFile("memory_store.json"),
    AGENT_WORKSPACE_DIR: dataFile("agent_workspace"),
    PLUGIN_STORE_PATH: dataFile("plugin_store.json"),
    PLUGIN_WORKSPACE_DIR: dataFile("plugin_workspaces"),
    PLUGIN_KEY_PATH: dataFile("plugin.key"),
    ATTACHMENT_STORAGE_DIR: dataFile("attachments_tmp"),
    KNOWLEDGE_STORE_PATH: dataFile("knowledge_vectors.json"),
    KNOWLEDGE_DOCUMENTS_PATH: dataFile("knowledge_documents.json"),
    VIDEO_STORAGE_DIR: dataFile("videos"),
    OAUTH_CREDENTIALS_DIR: dataFile("oauth"),
    BILLING_STORE_PATH: dataFile("billing_store.json"),
    TOKEN_STORE_PATH: dataFile("token_store.json"),
    PROFILE_STORE_PATH: dataFile("profile_store.json"),
  };
}
class BackendManager {
  constructor({ url = DEFAULT_BACKEND_URL, isPackaged, resourcesPath, electronDir, onLog, extraEnv } = {}) {
    this.url = url;
    this.isPackaged = Boolean(isPackaged);
    this.resourcesPath = resourcesPath;
    this.electronDir = electronDir;
    this.onLog = onLog || (() => {});
    // Extra environment variables merged on top of process.env when
    // spawning the backend - e.g. CORS_ALLOWED_ORIGINS computed from the
    // actual resolved frontend origin, so a renderer fetch() is never
    // silently blocked by CORS even if the static server fell back to a
    // non-default port.
    this.extraEnv = extraEnv || {};
    this.process = null;
    this.spawnedByUs = false;
  }
  /** Returns true once the backend answers /health, spawning it if needed. */
  async ensureRunning() {
    if (await probeBackend(this.url)) {
      this.onLog("Backend already reachable at " + this.url + " - reusing it.");
      return true;
    }
    const cwd = resolveBackendCwd({
      isPackaged: this.isPackaged,
      resourcesPath: this.resourcesPath,
      electronDir: this.electronDir,
    });
    const python = resolvePythonExecutable(cwd);
    const { hostname, port } = new URL(this.url);
    // Always loopback for Electron-spawned backend. LAN bind requires an
    // explicit opt-in (misconfiguration must not expose auth cookies / agent).
    const allowLan = String(process.env.NEXA_ELECTRON_ALLOW_LAN_BIND || "").trim() === "1";
    const bindHost = allowLan
      ? (hostname === "0.0.0.0" || hostname === "::" ? "0.0.0.0" : hostname || "localhost")
      : (hostname === "localhost" ? "localhost" : "127.0.0.1");
    this.onLog(`Starting backend: ${python} -m uvicorn app.main:app --host ${bindHost} --port ${port} (cwd=${cwd})`);
    try {
      this.process = spawn(
        python,
        ["-m", "uvicorn", "app.main:app", "--host", bindHost, "--port", String(port)],
        {
          cwd,
          env: { ...process.env, ...this.extraEnv },
          windowsHide: true,
        }
      );
      this.spawnedByUs = true;
    } catch (err) {
      this.onLog(`Failed to spawn backend process: ${err && err.message}`);
      return false;
    }
    this.process.stdout?.on("data", (chunk) => this.onLog(`[backend] ${chunk.toString().trimEnd()}`));
    this.process.stderr?.on("data", (chunk) => this.onLog(`[backend] ${chunk.toString().trimEnd()}`));
    this.process.on("exit", (code) => {
      this.onLog(`Backend process exited with code ${code}`);
      this.process = null;
    });
    const deadline = Date.now() + MAX_STARTUP_WAIT_MS;
    while (Date.now() < deadline) {
      if (await probeBackend(this.url)) return true;
      await sleep(STARTUP_POLL_INTERVAL_MS);
    }
    this.onLog("Backend did not become healthy within the startup window.");
    return false;
  }
  /** Stops the backend only if this manager started it. */
  stop() {
    if (this.spawnedByUs && this.process && !this.process.killed) {
      this.onLog("Stopping backend process started by this app.");
      this.process.kill();
    }
    this.process = null;
  }
}
module.exports = {
  BackendManager,
  probeBackend,
  resolveBackendCwd,
  resolvePythonExecutable,
  resolveDesktopStorageEnv,
  migrateLegacyData,
  normalizeLoopbackBackendUrl,
  DEFAULT_BACKEND_URL,
};
