"use client";
import { create } from "zustand";
import type { AuthStatus, AuthUser, RegisterPayload } from "@/lib/auth-api";
import {
  fetchAuthStatus,
  fetchMe,
  loginAccount,
  logoutAccount,
  registerAccount,
  resendVerificationCode,
  resetPassword,
  forgotPassword,
  verifyEmail,
} from "@/lib/auth-api";

export type AuthScreen = "login" | "ownerSetup" | "verify" | "forgot" | "reset";

interface AuthState {
  status: "loading" | "authenticated" | "anonymous";
  user: AuthUser | null;
  authStatus: AuthStatus | null;
  screen: AuthScreen;
  pendingEmail: string;
  codeExpiresAt: string | null;
  resendAvailableAt: string | null;
  bootstrap: () => Promise<void>;
  setScreen: (screen: AuthScreen) => void;
  setPendingEmail: (email: string) => void;
  setupOwner: (payload: RegisterPayload) => Promise<void>;
  verify: (code: string) => Promise<void>;
  resend: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  requestReset: (email: string) => Promise<void>;
  confirmReset: (code: string, password: string, confirm: string) => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  status: "loading",
  user: null,
  authStatus: null,
  screen: "login",
  pendingEmail: "",
  codeExpiresAt: null,
  resendAvailableAt: null,

  setScreen: (screen) => set({ screen }),
  setPendingEmail: (email) => set({ pendingEmail: email }),

  bootstrap: async () => {
    try {
      const authStatus = await fetchAuthStatus();
      try {
        const { user } = await fetchMe();
        set({ status: "authenticated", user, authStatus, screen: "login" });
      } catch {
        set({
          status: "anonymous",
          user: null,
          authStatus,
          screen: authStatus.registration_open ? "ownerSetup" : "login",
        });
      }
    } catch {
      set({ status: "anonymous", user: null, authStatus: null, screen: "login" });
    }
  },

  setupOwner: async (payload) => {
    const result = await registerAccount(payload);
    if (result.ready) {
      set({
        status: "authenticated",
        user: result.user,
        screen: "login",
        authStatus: {
          single_user: true,
          has_user: true,
          registration_open: false,
          skip_email_verification: true,
        },
      });
      return;
    }
    set({
      status: "anonymous",
      user: null,
      screen: "verify",
      pendingEmail: result.email,
      codeExpiresAt: result.code_expires_at,
      resendAvailableAt: result.resend_available_at,
    });
  },

  verify: async (code) => {
    const email = get().pendingEmail;
    await verifyEmail(email, code);
    set({ screen: "login", codeExpiresAt: null });
  },

  resend: async () => {
    const email = get().pendingEmail;
    const result = await resendVerificationCode(email);
    set({
      codeExpiresAt: result.code_expires_at,
      resendAvailableAt: result.resend_available_at,
    });
  },

  login: async (email, password) => {
    try {
      const result = await loginAccount(email, password);
      set({ status: "authenticated", user: result.user, screen: "login" });
    } catch (err) {
      const code = (err as { code?: string })?.code;
      if (code === "EmailNotVerified") {
        set({ screen: "verify", pendingEmail: email.trim().toLowerCase() });
      }
      throw err;
    }
  },

  logout: async () => {
    try {
      await logoutAccount();
    } finally {
      const authStatus = get().authStatus;
      set({
        status: "anonymous",
        user: null,
        screen: authStatus?.registration_open ? "ownerSetup" : "login",
      });
    }
  },

  requestReset: async (email) => {
    const result = await forgotPassword(email);
    set({
      screen: "reset",
      pendingEmail: (result.email || email).trim().toLowerCase(),
      codeExpiresAt: result.code_expires_at ?? null,
      resendAvailableAt: result.resend_available_at ?? null,
    });
  },

  confirmReset: async (code, password, confirm) => {
    await resetPassword({
      email: get().pendingEmail,
      code,
      password,
      confirm_password: confirm,
    });
    set({ screen: "login", codeExpiresAt: null });
  },
}));
