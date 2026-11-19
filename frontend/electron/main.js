/**
 * NEXA desktop shell - Electron main process (Part 8.5).
 *
 * Wraps the existing Next.js frontend (Parts 1-8, unchanged) in a desktop
 * window and makes sure the existing FastAPI backend is running, without
 * duplicating either. Security posture: contextIsolation on, nodeIntegration
 * off, sandboxed preload, a restrictive CSP, external links always open in
 * the system browser, and a small validated IPC surface (see preload.js).
 */
"use strict";
const path = require("node:path");
const { app, BrowserWindow, Menu, Tray, shell, ipcMain, dialog, session } = require("electron");
const { BackendManager, DEFAULT_BACKEND_URL, resolveDesktopStorageEnv, migrateLegacyData } = require("./backend");
const { createLogger } = require("./log");
const { startStaticServer } = require("./static-server");
const FRONTEND_DEV_URL = "http://localhost:4820";
const BACKEND_URL = process.env.NEXA_BACKEND_URL || DEFAULT_BACKEND_URL;
const NEXA_BG_COLOR = "#0b0b12"; // matches NEXA's black/purple theme (globals.css)
let mainWindow = null;
let tray = null;
let backendManager = null;
let logger = null;
let appOrigin = null;
let staticServer = null;
function buildAppInfo() {
  return {
    name: "NEXA",
    version: app.getVersion(),
    electronVersion: process.versions.electron,
    chromeVersion: process.versions.chrome,
    nodeVersion: process.versions.node,
    platform: process.platform,
    packaged: app.isPackaged,
    buildDate: app.isPackaged ? app.getAppPath() && new Date().toISOString() : new Date().toISOString(),
  };
}
function resolveFrontendOutDir() {
  // Packaged: serve from extraResources/out (real filesystem — asar serves
  // are unreliable for the loopback static server on Windows).
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "out");
  }
  return path.join(__dirname, "..", "out");
}

function resolveIconPath() {
  // Dev: the Next.js public/ folder. Packaged: Next's static export copies
  // public/ assets to the root of out/ alongside index.html.
  return app.isPackaged
    ? path.join(process.resourcesPath, "out", "nexa-logo.png")
    : path.join(__dirname, "..", "public", "nexa-logo.png");
}
async function resolveStartUrl() {
  if (app.isPackaged) {
    // Next.js's static export uses absolute "/_next/..." asset paths, which
    // do not resolve correctly under a raw file:// load - serve `out/`
    // locally instead (127.0.0.1 only, fixed port, path-traversal safe).
    const outDir = resolveFrontendOutDir();
    const indexHtml = path.join(outDir, "index.html");
    if (!require("node:fs").existsSync(indexHtml)) {
      throw new Error(
        `Frontend build missing at ${indexHtml}. Reinstall NEXA or rebuild with NEXA_TARGET=electron.`
      );
    }
    logger && logger.write(`Serving frontend from ${outDir}`);
    staticServer = await startStaticServer(outDir);
    const addr = staticServer.address();
    const port = typeof addr === "object" && addr ? addr.port : 48420;
    logger && logger.write(`Static server listening on http://127.0.0.1:${port}/`);
    // localhost (not 127.0.0.1) so WebAuthn rpId=localhost matches the page origin.
    return `http://localhost:${port}/`;
  }
  return FRONTEND_DEV_URL;
}
/** CORS origins the backend accepts, always including the frontend's actual
 * resolved origin so a renderer fetch() is never silently blocked - even if
 * the static server had to fall back off its usual fixed port. */
function corsOriginsFor(origin) {
  const base = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:4820",
    "http://127.0.0.1:4820",
    "http://localhost:48420",
    "http://127.0.0.1:48420",
  ];
  if (!origin) return base.join(",");
  const extra = new Set([origin]);
  try {
    const url = new URL(origin);
    const altHost = url.hostname === "127.0.0.1" ? "localhost" : url.hostname === "localhost" ? "127.0.0.1" : null;
    if (altHost) extra.add(`${url.protocol}//${altHost}:${url.port}`);
  } catch {
    /* ignore - fall back to just the base list */
  }
  return [...base, ...extra].join(",");
}
function isSameOriginOrFile(targetUrl) {
  try {
    const target = new URL(targetUrl);
    if (target.protocol === "file:") return true;
    return appOrigin !== null && target.origin === appOrigin;
  } catch {
    return false;
  }
}
function applyContentSecurityPolicy() {
  // Browser STT (Chrome/Electron) may contact Google speech endpoints.
  const connectSrc = [
    "'self'",
    "http://127.0.0.1:8420",
    "http://localhost:8420",
    "http://localhost:4820",
    "http://127.0.0.1:48420",
    "http://localhost:48420",
    "http://127.0.0.1:11434",
    "http://localhost:11434",
    "https://www.google.com",
    "https://*.google.com",
    "https://*.googleapis.com",
    "https://*.gstatic.com",
    "wss://*.google.com",
    "wss://*.googleapis.com",
    process.env.NEXA_BACKEND_URL,
  ]
    .filter(Boolean)
    .join(" ");
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        "Content-Security-Policy": [
          "default-src 'self'; " +
            "img-src 'self' data: blob:; " +
            `connect-src ${connectSrc}; ` +
            "style-src 'self' 'unsafe-inline'; " +
            "script-src 'self' 'unsafe-inline'; " +
            "media-src 'self' blob: mediastream:; " +
            "object-src 'none'; " +
            "base-uri 'self'",
        ],
      },
    });
  });
}
function applyMediaPermissions() {
  const ses = session.defaultSession;
  const allowed = new Set(["media", "microphone", "audioCapture", "mediaKeySystem"]);
  ses.setPermissionRequestHandler((webContents, permission, callback, details) => {
    try {
      const requesting = details && details.requestingUrl ? new URL(details.requestingUrl) : null;
      const okOrigin =
        !requesting ||
        (appOrigin && requesting.origin === appOrigin) ||
        requesting.hostname === "127.0.0.1" ||
        requesting.hostname === "localhost";
      callback(Boolean(okOrigin && allowed.has(permission)));
    } catch {
      callback(false);
    }
  });
  ses.setPermissionCheckHandler((_webContents, permission, requestingOrigin) => {
    try {
      if (!allowed.has(permission)) return false;
      if (!requestingOrigin) return true;
      const url = new URL(requestingOrigin);
      if (appOrigin && url.origin === appOrigin) return true;
      return url.hostname === "127.0.0.1" || url.hostname === "localhost";
    } catch {
      return false;
    }
  });
}
async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 960,
    minHeight: 600,
    title: "NEXA",
    backgroundColor: NEXA_BG_COLOR,
    icon: resolveIconPath(),
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      spellcheck: false,
    },
  });
  mainWindow.once("ready-to-show", () => mainWindow && mainWindow.show());
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
  // Any link that isn't our own app origin opens in the system browser
  // instead of navigating the app window or creating a new BrowserWindow.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//i.test(url)) shell.openExternal(url);
    return { action: "deny" };
  });
  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (isSameOriginOrFile(url)) return;
    event.preventDefault();
    if (/^https?:\/\//i.test(url)) shell.openExternal(url);
  });
  // Editable fields need an explicit context menu — Chromium/Electron does
  // not show Cut/Copy/Paste on right-click by default in a custom shell.
  mainWindow.webContents.on("context-menu", (_event, params) => {
    const canEdit = params.isEditable;
    const items = [];
    if (canEdit) {
      items.push(
        { role: "undo", enabled: params.editFlags.canUndo },
        { role: "redo", enabled: params.editFlags.canRedo },
        { type: "separator" },
        { role: "cut", enabled: params.editFlags.canCut },
        { role: "copy", enabled: params.editFlags.canCopy },
        { role: "paste", enabled: params.editFlags.canPaste },
        { role: "selectAll", enabled: params.editFlags.canSelectAll }
      );
    } else if (params.selectionText && params.selectionText.trim()) {
      items.push({ role: "copy" });
    }
    if (!items.length) return;
    Menu.buildFromTemplate(items).popup({ window: mainWindow || undefined });
  });
  const startUrl = await resolveStartUrl();
  try {
    appOrigin = new URL(startUrl).origin;
  } catch {
    appOrigin = null;
  }
  // React update-depth / OOM crashes used to kill the renderer and leave
  // Chromium's "This page couldn't load" screen with no recovery path.
  mainWindow.webContents.on("render-process-gone", (_event, details) => {
    logger && logger.write(`Renderer gone (${details.reason}) - reloading UI`);
    setTimeout(() => {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.loadURL(startUrl).catch(() => undefined);
      }
    }, 400);
  });
  // Guard against the local static server (or, during dev, the Next.js
  // dev server) not yet accepting connections the instant the window
  // tries to load it - this showed up as a bare "This page couldn't load"
  // error screen with no automatic recovery. A few short, backed-off
  // retries fix it without the user having to click Reload themselves.
  const MAX_LOAD_RETRIES = 6;
  let loadRetryCount = 0;
  mainWindow.webContents.on("did-finish-load", () => {
    loadRetryCount = 0;
  });
  mainWindow.webContents.on("did-fail-load", (_event, errorCode, errorDescription, validatedURL, isMainFrame) => {
    // -3 is ERR_ABORTED, which fires on ordinary cancelled/interrupted
    // navigations (e.g. a manual reload) and must not be retried.
    if (!isMainFrame || errorCode === -3 || !mainWindow) return;
    if (loadRetryCount >= MAX_LOAD_RETRIES) {
      logger && logger.write(
        `Giving up loading ${validatedURL} after ${MAX_LOAD_RETRIES} retries (${errorDescription}, code ${errorCode}).`
      );
      dialog.showErrorBox(
        "This page couldn't load",
        `NEXA could not open its UI (${errorDescription}).\n\nURL: ${validatedURL}\n\nTry closing all NEXA windows and reopening the app.`
      );
      return;
    }
    loadRetryCount += 1;
    const delayMs = 300 * loadRetryCount;
    logger && logger.write(
      `Main frame failed to load (${errorDescription}, code ${errorCode}) - retrying in ${delayMs}ms ` +
        `(attempt ${loadRetryCount}/${MAX_LOAD_RETRIES}).`
    );
    setTimeout(() => {
      if (mainWindow) mainWindow.loadURL(startUrl);
    }, delayMs);
  });
  mainWindow.loadURL(startUrl);
}
function buildMenu() {
  const isMac = process.platform === "darwin";
  const template = [
    ...(isMac ? [{ role: "appMenu" }] : []),
    {
      label: "File",
      submenu: [isMac ? { role: "close" } : { role: "quit" }],
    },
    {
      label: "Edit",
      submenu: [
        { role: "undo" },
        { role: "redo" },
        { type: "separator" },
        { role: "cut" },
        { role: "copy" },
        { role: "paste" },
        { role: "selectAll" },
      ],
    },
    {
      label: "View",
      submenu: [
        { role: "reload" },
        { role: "resetZoom" },
        { role: "zoomIn" },
        { role: "zoomOut" },
        { type: "separator" },
        { role: "togglefullscreen" },
        ...(app.isPackaged ? [] : [{ role: "toggleDevTools" }]),
      ],
    },
    {
      label: "Window",
      submenu: [{ role: "minimize" }, { role: "zoom" }, { type: "separator" }, { role: "close" }],
    },
    {
      label: "Help",
      submenu: [
        {
          label: "About NEXA",
          click: showAboutDialog,
        },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}
function showAboutDialog() {
  const info = buildAppInfo();
  dialog.showMessageBox(mainWindow || undefined, {
    type: "info",
    title: "About NEXA",
    message: "NEXA",
    detail:
      `Think. Create. Act.\n\n` +
      `Version: ${info.version}\n` +
      `Electron: ${info.electronVersion}\n` +
      `Node: ${info.nodeVersion}\n` +
      `Platform: ${info.platform}`,
    buttons: ["OK"],
  });
}
/**
 * Keep packaged desktop accounts in Electron's per-user writable data
 * directory, not under the install/resources directory. On first launch
 * after this change, migrate the previous relative auth store if present.
 */
function prepareDesktopAuthStore() {
  const fs = require("node:fs");
  const userDataDir = app.getPath("userData");
  const storageEnv = resolveDesktopStorageEnv(userDataDir, process.env);
  const legacyRoot = app.isPackaged
    ? path.join(process.resourcesPath, "backend")
    : path.join(__dirname, "..", "..");
  migrateLegacyData({
    legacyRoot,
    userDataDir,
    onLog: (message) => logger && logger.write(message),
  });
  const target = storageEnv.AUTH_STORE_PATH;
  if (fs.existsSync(target)) {
    try {
      fs.chmodSync(target, 0o600);
    } catch {
      // Windows ACLs are inherited from the per-user Electron data directory.
    }
  }
  return storageEnv;
}
function createTray() {
  try {
    tray = new Tray(resolveIconPath());
    tray.setToolTip("NEXA - Think. Create. Act.");
    tray.setContextMenu(
      Menu.buildFromTemplate([
        {
          label: "Show NEXA",
          click: () => {
            if (mainWindow) {
              mainWindow.show();
              mainWindow.focus();
            }
          },
        },
        { type: "separator" },
        { label: "Quit", click: () => app.quit() },
      ])
    );
    tray.on("click", () => {
      if (mainWindow) {
        mainWindow.show();
        mainWindow.focus();
      }
    });
  } catch (err) {
    logger && logger.write(`Tray icon unavailable: ${err && err.message}`);
  }
}
function registerIpcHandlers() {
  ipcMain.handle("nexa:get-app-info", () => buildAppInfo());
  ipcMain.handle("nexa:get-backend-status", async () => {
    const { probeBackend } = require("./backend");
    const reachable = await probeBackend(BACKEND_URL, 1500);
    return { url: BACKEND_URL, reachable };
  });
  ipcMain.handle("nexa:open-external", (_event, url) => {
    if (typeof url !== "string" || !/^https?:\/\//i.test(url)) {
      throw new Error("Rejected: only http(s) URLs may be opened externally.");
    }
    return shell.openExternal(url);
  });
  ipcMain.handle("nexa:toggle-devtools", (event) => {
    // Packaged builds must not expose DevTools to arbitrary renderer pages.
    if (app.isPackaged && process.env.NEXA_ALLOW_PACKAGED_DEVTOOLS !== "1") {
      return { open: false, denied: true };
    }
    const win = BrowserWindow.fromWebContents(event.sender);
    if (!win) return { open: false };
    const wc = win.webContents;
    if (wc.isDevToolsOpened()) {
      wc.closeDevTools();
      return { open: false };
    }
    wc.openDevTools({ mode: "detach" });
    return { open: true };
  });
  /**
   * Open an allowlisted local file with the OS default app.
   * Payload: { path: string, confirm?: boolean }
   * - Path must stay under the NEXA agent_workspace (or NEXA_DESKTOP_ALLOWED_DIRS).
   * - Without confirm=true, shows a native confirmation dialog.
   * - Never executes shell commands or opens arbitrary paths.
   */
  ipcMain.handle("nexa:open-path", async (event, payload) => {
    const filePath = payload && typeof payload.path === "string" ? payload.path : "";
    // Renderer-supplied flags are not trusted as authorization to bypass a native confirmation.
    const confirm = false;
    if (!filePath || filePath.includes("\0")) {
      throw new Error("Rejected: invalid path.");
    }
    const pathMod = require("node:path");
    const fsMod = require("node:fs");
    const resolved = pathMod.resolve(filePath);
    const roots = [];
    // Packaged/dev: prefer workspace next to backend cwd / repo.
    const workspaceCandidates = [
      pathMod.join(app.getPath("userData"), "agent_workspace"),
      pathMod.join(__dirname, "..", "..", "agent_workspace"),
    ];
    for (const root of workspaceCandidates) {
      try {
        roots.push(fsMod.realpathSync.native ? fsMod.realpathSync.native(root) : fsMod.realpathSync(root));
      } catch {
        roots.push(pathMod.resolve(root));
      }
    }
    const extra = (process.env.NEXA_DESKTOP_ALLOWED_DIRS || "")
      .split(pathMod.delimiter)
      .map((p) => p.trim())
      .filter(Boolean);
    for (const root of extra) {
      try {
        roots.push(fsMod.realpathSync(root));
      } catch {
        /* skip missing allowlist entries */
      }
    }
    let realTarget;
    try {
      realTarget = fsMod.existsSync(resolved) ? fsMod.realpathSync(resolved) : resolved;
    } catch {
      throw new Error("Rejected: cannot resolve path.");
    }
    const allowed = roots.some((root) => {
      const rel = pathMod.relative(root, realTarget);
      return rel && !rel.startsWith("..") && !pathMod.isAbsolute(rel);
    });
    // Also allow if target is directly under a root that may not exist yet as realpath.
    const allowedLoose = roots.some((root) => realTarget === root || realTarget.startsWith(root + pathMod.sep));
    if (!allowed && !allowedLoose) {
      throw new Error("Rejected: path is outside allowlisted NEXA directories.");
    }
    if (!fsMod.existsSync(realTarget) || !fsMod.statSync(realTarget).isFile()) {
      throw new Error("Rejected: path is not an existing file.");
    }
    if (!confirm) {
      const win = BrowserWindow.fromWebContents(event.sender);
      const result = await dialog.showMessageBox(win || undefined, {
        type: "question",
        buttons: ["Cancel", "Open"],
        defaultId: 1,
        cancelId: 0,
        title: "Open file?",
        message: "Open this file with the default application?",
        detail: realTarget,
      });
      if (result.response !== 1) {
        return { opened: false, cancelled: true, path: realTarget };
      }
    }
    const err = await shell.openPath(realTarget);
    if (err) {
      throw new Error(`Failed to open path: ${err}`);
    }
    return { opened: true, path: realTarget };
  });
}
const gotSingleInstanceLock = app.requestSingleInstanceLock();
if (!gotSingleInstanceLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });
  app.whenReady().then(async () => {
    logger = createLogger(path.join(app.getPath("userData"), "logs"));
    logger.write(`NEXA desktop starting (packaged=${app.isPackaged}, platform=${process.platform})`);
    applyContentSecurityPolicy();
    applyMediaPermissions();
    registerIpcHandlers();
    buildMenu();
    try {
      await createWindow();
    } catch (err) {
      logger.write(`Failed to create window: ${err && err.stack ? err.stack : err}`);
      dialog.showErrorBox(
        "NEXA failed to open",
        (err && err.message) ||
          "The desktop shell could not start its local UI server. Try reinstalling NEXA."
      );
      app.quit();
      return;
    }
    createTray();
    const desktopStorageEnv = prepareDesktopAuthStore();
    backendManager = new BackendManager({
      url: BACKEND_URL,
      isPackaged: app.isPackaged,
      resourcesPath: process.resourcesPath,
      electronDir: __dirname,
      onLog: (line) => logger.write(line),
      extraEnv: {
        ...desktopStorageEnv,
        CORS_ALLOWED_ORIGINS: corsOriginsFor(appOrigin),
        // Prefer live Ollama when available; override via process env if set.
        AI_PROVIDER: process.env.AI_PROVIDER || "ollama",
        LOCAL_MODEL_URL: process.env.LOCAL_MODEL_URL || "http://localhost:11434",
        LOCAL_MODEL_NAME: process.env.LOCAL_MODEL_NAME || "llama3.2:3b",
        NEXA_STORAGE_MODE: process.env.NEXA_STORAGE_MODE || "persistent",
        // Do not fake Vision/Create on desktop — require real keys/providers.
        VISION_PROVIDER: process.env.VISION_PROVIDER || "none",
        IMAGE_PROVIDER: process.env.IMAGE_PROVIDER || "none",
        // Local Electron backend may perform allowlisted OS file open / local_files.
        NEXA_LOCAL_DESKTOP: process.env.NEXA_LOCAL_DESKTOP || "1",
      },
    });
    const healthy = await backendManager.ensureRunning();
    if (!healthy) {
      dialog.showErrorBox(
        "NEXA backend did not start",
        "NEXA could not reach its backend service. Make sure Python 3.12+ is installed, " +
          "or start it manually (see README.md), then reopen NEXA."
      );
    }
  });
  app.on("window-all-closed", () => {
    if (process.platform !== "darwin") app.quit();
  });
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) void createWindow();
  });
  app.on("before-quit", () => {
    if (backendManager) backendManager.stop();
    if (staticServer) staticServer.close();
  });
}
