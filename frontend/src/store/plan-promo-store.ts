/**
 * Plan upgrade prompts — shown when NEXA credits run out, or occasionally.
 * Never permanently stuck in the sidebar (that blocked Settings / profile).
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

export const TOKEN_WAIT_MS = 10 * 60 * 60 * 1000; // 10 hours
const SOFT_COOLDOWN_MS = 24 * 60 * 60 * 1000;
const SOFT_CHANCE = 0.22;

const TOKEN_LIMIT_CODES = new Set([
  "InsufficientTokens",
  "DailyTokenLimitExceeded",
  "MonthlyTokenLimitExceeded",
]);

export function isTokenLimitErrorCode(code: string | undefined): boolean {
  return Boolean(code && TOKEN_LIMIT_CODES.has(code));
}

type PromoMode = "hidden" | "limit" | "soft";

interface PlanPromoState {
  mode: PromoMode;
  /** Epoch ms when free credits may be tried again after a limit hit. */
  waitUntil: number | null;
  lastSoftShownAt: number | null;
  openLimit: () => void;
  openSoftMaybe: () => void;
  dismiss: () => void;
  /** Call when API returns a token-limit error. */
  notifyTokenLimit: () => void;
}

export const usePlanPromoStore = create<PlanPromoState>()(
  persist(
    (set, get) => ({
      mode: "hidden",
      waitUntil: null,
      lastSoftShownAt: null,

      openLimit: () => {
        const waitUntil = Date.now() + TOKEN_WAIT_MS;
        set({ mode: "limit", waitUntil });
      },

      notifyTokenLimit: () => {
        get().openLimit();
      },

      openSoftMaybe: () => {
        const { mode, waitUntil, lastSoftShownAt } = get();
        if (mode === "limit") return;
        if (waitUntil && Date.now() < waitUntil) return;
        if (lastSoftShownAt && Date.now() - lastSoftShownAt < SOFT_COOLDOWN_MS) return;
        if (Math.random() > SOFT_CHANCE) return;
        set({ mode: "soft", lastSoftShownAt: Date.now() });
      },

      dismiss: () => set({ mode: "hidden" }),
    }),
    {
      name: "nexa-plan-promo",
      partialize: (s) => ({
        waitUntil: s.waitUntil,
        lastSoftShownAt: s.lastSoftShownAt,
        // Re-open limit dialog on reload if still waiting.
        mode: s.waitUntil && s.waitUntil > Date.now() ? ("limit" as const) : ("hidden" as const),
      }),
    },
  ),
);
