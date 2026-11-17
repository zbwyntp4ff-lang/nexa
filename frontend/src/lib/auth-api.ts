/** Auth API types + helpers (server-side sessions via httpOnly cookie). */
import { API_BASE_URL, ApiError, request } from "./api";

export interface AuthConsent {
  document: string;
  version: string;
  accepted_at: string;
}

export interface AuthUser {
  id: string;
  first_name: string;
  last_name: string;
  username: string;
  email: string;
  email_verified: boolean;
  is_active: boolean;
  is_owner?: boolean;
  consents: AuthConsent[];
  created_at: string;
}

export interface RegisterPayload {
  first_name: string;
  last_name: string;
  username: string;
  email: string;
  password: string;
  confirm_password: string;
  accept_terms: boolean;
  accept_privacy: boolean;
  accept_license: boolean;
}

export interface RegisterResult {
  user: AuthUser;
  email: string;
  verification_id: string;
  code_expires_at: string;
  resend_available_at: string;
  ready?: boolean;
  message: string;
}

export interface AuthStatus {
  single_user: boolean;
  has_user: boolean;
  registration_open: boolean;
  skip_email_verification: boolean;
}

export function fetchAuthStatus(signal?: AbortSignal) {
  return request<AuthStatus>("/api/v1/auth/status", { signal });
}

/** First-run owner setup only when there is no account yet. Existing users see login. */
export function initialAuthScreen(status: AuthStatus | null): "login" | "ownerSetup" {
  if (status?.has_user === false && status.registration_open) return "ownerSetup";
  return "login";
}

export interface VerifyResult {
  user: AuthUser;
  message: string;
}

export interface ResendResult {
  email: string;
  sent: boolean;
  already_verified: boolean;
  code_expires_at: string | null;
  resend_available_at: string;
  message: string;
}

export interface LoginResult {
  user: AuthUser;
  expires_at: string;
  message: string;
}

export function registerAccount(payload: RegisterPayload, signal?: AbortSignal) {
  return request<RegisterResult>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

export function verifyEmail(email: string, code: string, signal?: AbortSignal) {
  return request<VerifyResult>("/api/v1/auth/verify-email", {
    method: "POST",
    body: JSON.stringify({ email, code }),
    signal,
  });
}

export function resendVerificationCode(email: string, signal?: AbortSignal) {
  return request<ResendResult>("/api/v1/auth/resend-code", {
    method: "POST",
    body: JSON.stringify({ email }),
    signal,
  });
}

export function loginAccount(email: string, password: string, signal?: AbortSignal) {
  return request<LoginResult>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
    signal,
  });
}

export function logoutAccount(signal?: AbortSignal) {
  return request<{ message: string }>("/api/v1/auth/logout", {
    method: "POST",
    signal,
  });
}

export function deleteAccount(signal?: AbortSignal) {
  return request<{ deleted: boolean; report?: Record<string, unknown> }>(
    "/api/v1/auth/account",
    {
      method: "DELETE",
      body: JSON.stringify({ confirm: "DELETE" }),
      signal,
    },
  );
}

export function fetchMe(signal?: AbortSignal) {
  return request<{ user: AuthUser }>("/api/v1/auth/me", { signal });
}

export function forgotPassword(email: string, signal?: AbortSignal) {
  return request<{
    message: string;
    email?: string;
    code_expires_at?: string;
    resend_available_at?: string;
  }>("/api/v1/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
    signal,
  });
}

export function resetPassword(
  payload: {
    email: string;
    code: string;
    password: string;
    confirm_password: string;
  },
  signal?: AbortSignal,
) {
  return request<{ message: string }>("/api/v1/auth/reset-password", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

export function isAuthApiError(err: unknown): err is ApiError {
  return err instanceof ApiError;
}

export type OAuthProviderId = "google" | "github" | "apple";

export interface ProviderInfo {
  id: string;
  label: string;
  enabled: boolean;
  kind: string;
}

export interface ProvidersResult {
  oauth: ProviderInfo[];
  device: ProviderInfo;
  passkey: ProviderInfo;
  password: ProviderInfo;
}

export function fetchAuthProviders(signal?: AbortSignal) {
  return request<ProvidersResult>("/api/v1/auth/providers", { signal });
}

export function startOAuth(provider: OAuthProviderId, signal?: AbortSignal) {
  return request<{ authorize_url: string; state: string; provider: string }>(
    `/api/v1/auth/oauth/${provider}/start`,
    { signal },
  );
}

export interface DeviceStartResult {
  device_code: string;
  user_code: string;
  verification_uri: string;
  verification_uri_complete: string;
  expires_in: number;
  interval: number;
  qr_payload: string;
  qr_svg?: string;
  phone_url?: string;
}

export function startDeviceLogin(signal?: AbortSignal) {
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  return request<DeviceStartResult>("/api/v1/auth/device/start", {
    method: "POST",
    body: JSON.stringify({ origin }),
    signal,
  });
}

export type LegalHolderKind = "individual" | "sole_proprietor" | "company";

export interface LegalHolder {
  name: string;
  kind: LegalHolderKind;
  kind_label: string;
  contact: string;
  inn: string;
  country: string;
  year: number;
}

export function fetchLegalIndex(signal?: AbortSignal) {
  return request<{
    documents: { id: string; version: string; source: string }[];
    holder: LegalHolder;
  }>("/api/v1/auth/legal", { signal });
}

export function fetchLegalDocument(docId: string, signal?: AbortSignal) {
  return request<{ id: string; version: string; source: string; body: string }>(
    `/api/v1/auth/legal/${docId}`,
    { signal },
  );
}

export function saveLegalHolder(
  body: {
    name: string;
    kind: LegalHolderKind;
    contact?: string;
    inn?: string;
    country?: string;
  },
  signal?: AbortSignal,
) {
  return request<{ ok: boolean; holder: LegalHolder }>("/api/v1/auth/legal/holder", {
    method: "PUT",
    body: JSON.stringify(body),
    signal,
  });
}

export function saveGoogleOAuthConfig(clientId: string, clientSecret: string, signal?: AbortSignal) {
  return request<{ ok: boolean; enabled: boolean }>("/api/v1/auth/oauth/google/config", {
    method: "POST",
    body: JSON.stringify({ client_id: clientId, client_secret: clientSecret }),
    signal,
  });
}

export function pollDeviceLogin(deviceCode: string, signal?: AbortSignal) {
  return request<LoginResult>("/api/v1/auth/device/poll", {
    method: "POST",
    body: JSON.stringify({ device_code: deviceCode }),
    signal,
  });
}

export function approveDeviceLogin(userCode: string, signal?: AbortSignal) {
  return request<{ message: string }>("/api/v1/auth/device/approve", {
    method: "POST",
    body: JSON.stringify({ user_code: userCode }),
    signal,
  });
}

export function passkeyLoginOptions(signal?: AbortSignal) {
  return request<{
    challenge: string;
    timeout: number;
    rpId: string;
    userVerification: string;
    allowCredentials: { type: string; id: string }[];
  }>("/api/v1/auth/passkey/login/options", { method: "POST", signal });
}

export function passkeyLoginVerify(
  payload: { credential_id: string; client_data_json: string },
  signal?: AbortSignal,
) {
  return request<LoginResult>("/api/v1/auth/passkey/login/verify", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

export function passkeyRegisterOptions(signal?: AbortSignal) {
  return request<Record<string, unknown>>("/api/v1/auth/passkey/register/options", {
    method: "POST",
    signal,
  });
}

export function passkeyRegisterVerify(
  payload: {
    credential_id: string;
    client_data_json: string;
    public_key?: string;
    label?: string;
  },
  signal?: AbortSignal,
) {
  return request<{ message: string }>("/api/v1/auth/passkey/register/verify", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

/** Re-export for callers that need the backend origin. */
export { API_BASE_URL };
