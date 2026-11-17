/**
 * Browser sessions use only the server-set HttpOnly cookie.
 * Never persist session credentials in JavaScript-accessible storage.
 * This compatibility helper intentionally adds no Authorization header.
 */
const LEGACY_SESSION_KEY = "nexa_session_token";

// Remove tokens written by older NEXA versions. Do not read or reuse them:
// browser JavaScript must never regain access to a live session credential.
if (typeof window !== "undefined") {
  try {
    window.localStorage.removeItem(LEGACY_SESSION_KEY);
  } catch {
    // Storage may be disabled; cookie-based authentication still works.
  }
}

export function authHeaders(extra?: HeadersInit): HeadersInit {
  return extra ?? {};
}
