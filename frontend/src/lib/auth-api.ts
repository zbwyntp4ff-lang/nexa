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

/** Re-export for callers that need the backend origin. */
export { API_BASE_URL };
