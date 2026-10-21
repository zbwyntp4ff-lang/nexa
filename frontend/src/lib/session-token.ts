/** Client-side session token for desktop (Electron) where cookies may not
 * stick across localhost vs 127.0.0.1. Cookie auth still preferred when present.
 */
const STORAGE_KEY = "nexa_session_token";

export function getSessionToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return value && value.trim() ? value.trim() : null;
  } catch {
    return null;
  }
}

export function setSessionToken(token: string | null | undefined): void {
  if (typeof window === "undefined") return;
  try {
    if (!token || !token.trim()) {
      window.localStorage.removeItem(STORAGE_KEY);
      return;
    }
    window.localStorage.setItem(STORAGE_KEY, token.trim());
  } catch {
    // private mode / quota — cookie-only fallback
  }
}

export function clearSessionToken(): void {
  setSessionToken(null);
}

export function authHeaders(extra?: HeadersInit): HeadersInit {
  const token = getSessionToken();
  const base: Record<string, string> = {};
  if (token) base.Authorization = `Bearer ${token}`;
  if (!extra) return base;
  if (extra instanceof Headers) {
    const merged = new Headers(extra);
    if (token && !merged.has("Authorization")) merged.set("Authorization", `Bearer ${token}`);
    return merged;
  }
  if (Array.isArray(extra)) {
    return token && !extra.some(([k]) => k.toLowerCase() === "authorization")
      ? [...extra, ["Authorization", `Bearer ${token}`]]
      : extra;
  }
  return { ...base, ...extra };
}
