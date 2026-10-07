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
const { BackendManager, DEFAULT_BACKEND_URL } = require("./backend");
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
    return `http://127.0.0.1:${port}/`;
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
  const connectSrc = [
    "'self'",
    "http://127.0.0.1:8420",
    "http://localhost:8420",
    "http://localhost:4820",
    "http://127.0.0.1:11434",
    "http://localhost:11434",
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
            "img-src 'self' data: blob: http: https:; " +
            `connect-src ${connectSrc}; ` +
            "style-src 'self' 'unsafe-inline'; " +
            "script-src 'self' 'unsafe-inline'; " +
            "object-src 'none'; " +
            "base-uri 'self'",
        ],
      },
    });
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
    backendManager = new BackendManager({
      url: BACKEND_URL,
      isPackaged: app.isPackaged,
      resourcesPath: process.resourcesPath,
      electronDir: __dirname,
      onLog: (line) => logger.write(line),
      extraEnv: {
        CORS_ALLOWED_ORIGINS: corsOriginsFor(appOrigin),
        // Prefer live Ollama when available; override via process env if set.
        AI_PROVIDER: process.env.AI_PROVIDER || "ollama",
        LOCAL_MODEL_URL: process.env.LOCAL_MODEL_URL || "http://localhost:11434",
        LOCAL_MODEL_NAME: process.env.LOCAL_MODEL_NAME || "llama3.2:3b",
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
