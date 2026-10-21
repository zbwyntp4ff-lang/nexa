/**
 * Preload script for the NEXA desktop shell (Part 8.5).
 *
 * Runs with contextIsolation + sandbox enabled: it can only expose a fixed,
 * validated surface to the page via `contextBridge`. There is no generic
 * "invoke any IPC channel" passthrough - every method here maps to exactly
 * one main-process handler with its own validation, so renderer/web
 * content (including any injected script) can never reach an arbitrary
 * main-process capability.
 */
"use strict";
const { contextBridge, ipcRenderer } = require("electron");
const ALLOWED_EXTERNAL_URL = /^https?:\/\//i;
contextBridge.exposeInMainWorld("nexa", {
  isDesktop: true,
  getAppInfo: () => ipcRenderer.invoke("nexa:get-app-info"),
  getBackendStatus: () => ipcRenderer.invoke("nexa:get-backend-status"),
  openExternal: (url) => {
    if (typeof url !== "string" || !ALLOWED_EXTERNAL_URL.test(url)) {
      return Promise.reject(new Error("openExternal only accepts http(s) URLs."));
    }
    return ipcRenderer.invoke("nexa:open-external", url);
  },
  /**
   * Open an allowlisted local file via the OS default app.
   * Main process re-validates the path; confirm=false shows a native dialog.
   */
  openPath: (filePath, opts) => {
    if (typeof filePath !== "string" || !filePath.trim() || filePath.includes("\0")) {
      return Promise.reject(new Error("openPath requires a non-empty file path string."));
    }
    // Block obvious UNC / protocol smuggling in the renderer before IPC.
    if (/^(file:|https?:|javascript:)/i.test(filePath.trim())) {
      return Promise.reject(new Error("openPath accepts filesystem paths only, not URLs."));
    }
    return ipcRenderer.invoke("nexa:open-path", {
      path: filePath,
      confirm: !!(opts && opts.confirm),
    });
  },
  toggleDevTools: () => ipcRenderer.invoke("nexa:toggle-devtools"),
});
