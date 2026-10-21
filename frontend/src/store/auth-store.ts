"use client";
import { create } from "zustand";
import type { AuthStatus, AuthUser, RegisterPayload } from "@/lib/auth-api";
import {
  fetchAuthStatus,
  fetchMe,
  initialAuthScreen,
  deleteAccount,
  loginAccount,
  logoutAccount,
  registerAccount,
  resendVerificationCode,
  resetPassword,
  forgotPassword,
  verifyEmail,
} from "@/lib/auth-api";
import { clearSessionToken, setSessionToken } from "@/lib/session-token";
import { useChatStore } from "@/store/chat-store";

function bindChatUser(userId: string | null) {
  try {
    const chat = useChatStore.getState();
    chat.bindUser(userId);
    if (userId) {
      void chat.hydrateFromServer();
    }
  } catch {
    /* chat store may be unavailable during SSR */
  }
}

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
  deleteMyAccount: () => Promise<void>;
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
        bindChatUser(user.id);
        set({ status: "authenticated", user, authStatus, screen: "login" });
      } catch {
        clearSessionToken();
        bindChatUser(null);
        set({
          status: "anonymous",
          user: null,
          authStatus,
          screen: initialAuthScreen(authStatus),
        });
      }
    } catch {
      bindChatUser(null);
      set({ status: "anonymous", user: null, authStatus: null, screen: "login" });
    }
  },

  setupOwner: async (payload) => {
    const result = await registerAccount(payload);
    if (result.ready) {
      setSessionToken(result.session_token);
      let authStatus = get().authStatus;
      try {
        authStatus = await fetchAuthStatus();
      } catch {
        authStatus = {
          single_user: authStatus?.single_user ?? false,
          has_user: true,
          registration_open: authStatus?.registration_open ?? true,
          skip_email_verification: authStatus?.skip_email_verification ?? true,
        };
      }
      bindChatUser(result.user.id);
      set({
        status: "authenticated",
        user: result.user,
        screen: "login",
        authStatus,
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
      setSessionToken(result.session_token);
      bindChatUser(result.user.id);
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
      clearSessionToken();
      bindChatUser(null);
      const authStatus = get().authStatus;
      set({
        status: "anonymous",
        user: null,
        screen: initialAuthScreen(authStatus ?? null),
      });
    }
  },

  deleteMyAccount: async () => {
    const userId = get().user?.id;
    await deleteAccount();
    clearSessionToken();
    if (userId) {
      try {
        const chat = useChatStore.getState();
        const buckets = { ...chat.buckets };
        delete buckets[userId];
        useChatStore.setState({
          buckets,
          ownerUserId: null,
          conversations: [],
          activeConversationId: null,
          projects: [],
        });
      } catch {
        bindChatUser(null);
      }
    } else {
      bindChatUser(null);
    }
    let authStatus = get().authStatus;
    try {
      authStatus = await fetchAuthStatus();
    } catch {
      /* keep prior */
    }
    set({
      status: "anonymous",
      user: null,
      authStatus,
      screen: initialAuthScreen(authStatus ?? null),
    });
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
