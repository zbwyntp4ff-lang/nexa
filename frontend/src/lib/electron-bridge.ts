/**
 * Typed access to the desktop bridge exposed by `electron/preload.js`.
 *
 * Always returns sensible fallbacks when running in a normal browser (the
 * web preview / Cloud Agent view) - nothing here assumes Electron exists.
 */
export interface NexaAppInfo {
  name: string;
  version: string;
  electronVersion: string;
  chromeVersion: string;
  nodeVersion: string;
  platform: string;
  packaged: boolean;
  buildDate: string;
}
export interface NexaBackendStatus {
  url: string;
  reachable: boolean;
}
interface NexaDesktopBridge {
  isDesktop: true;
  getAppInfo: () => Promise<NexaAppInfo>;
  getBackendStatus: () => Promise<NexaBackendStatus>;
  openExternal: (url: string) => Promise<void>;
  toggleDevTools?: () => Promise<{ open: boolean }>;
}
declare global {
  interface Window {
    nexa?: NexaDesktopBridge;
  }
}
export function isDesktopApp(): boolean {
  return typeof window !== "undefined" && Boolean(window.nexa?.isDesktop);
}
export async function getDesktopAppInfo(): Promise<NexaAppInfo | null> {
  if (!isDesktopApp()) return null;
  try {
    return (await window.nexa!.getAppInfo()) ?? null;
  } catch {
    return null;
  }
}
export async function getDesktopBackendStatus(): Promise<NexaBackendStatus | null> {
  if (!isDesktopApp()) return null;
  try {
    return (await window.nexa!.getBackendStatus()) ?? null;
  } catch {
    return null;
  }
}
/** Opens a URL in the system browser when running as a desktop app; falls
 * back to a normal same-tab navigation in the browser preview. */
export function openExternalLink(url: string): void {
  if (isDesktopApp()) {
    void window.nexa!.openExternal(url).catch(() => {
      window.open(url, "_blank", "noopener,noreferrer");
    });
    return;
  }
  window.open(url, "_blank", "noopener,noreferrer");
}

/** GitHub main site + Desktop install page (system browser). */
export const GITHUB_HOME_URL = "https://github.com";
export const GITHUB_INSTALL_URL = "https://desktop.github.com/";

export function openGithubHomeAndInstall(): void {
  openExternalLink(GITHUB_HOME_URL);
  // Slight delay so the OS opens both tabs/windows reliably.
  window.setTimeout(() => openExternalLink(GITHUB_INSTALL_URL), 250);
}

/** Owner-only: open Chromium DevTools in the desktop shell. */
export async function toggleDesktopDevTools(): Promise<boolean> {
  if (!isDesktopApp() || !window.nexa?.toggleDevTools) return false;
  try {
    const result = await window.nexa.toggleDevTools();
    return Boolean(result?.open);
  } catch {
    return false;
  }
}
