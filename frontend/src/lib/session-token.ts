/**
 * Browser sessions use only the server-set HttpOnly cookie.
 * Never persist session credentials in JavaScript-accessible storage.
 * This compatibility helper intentionally adds no Authorization header.
 */
export function authHeaders(extra?: HeadersInit): HeadersInit {
  return extra ?? {};
}
