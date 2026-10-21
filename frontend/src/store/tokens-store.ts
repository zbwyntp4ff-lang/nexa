/**
 * Session cache for Tokens & Limits — survives settings-tab remounts so the
 * panel does not flash a full-page spinner on every visit.
 */
import { create } from "zustand";
import {
  fetchTokenBalance,
  fetchTokenHistory,
  isTokensApiError,
  type LedgerEntry,
  type TokenBalance,
} from "@/lib/tokens-api";

type LoadPhase = "idle" | "loading" | "refreshing";

interface TokensState {
  balance: TokenBalance | null;
  history: LedgerEntry[];
  error: string | null;
  phase: LoadPhase;
  /** Monotonic id so stale responses never win. */
  generation: number;
  load: (opts?: { soft?: boolean; errorMessage?: (err: unknown) => string }) => Promise<void>;
  reset: () => void;
}

export const useTokensStore = create<TokensState>((set, get) => ({
  balance: null,
  history: [],
  error: null,
  phase: "idle",
  generation: 0,

  reset: () =>
    set({
      balance: null,
      history: [],
      error: null,
      phase: "idle",
    }),

  load: async (opts) => {
    const soft = opts?.soft === true || get().balance !== null;
    const generation = get().generation + 1;
    set({
      generation,
      phase: soft ? "refreshing" : "loading",
      error: null,
    });
    try {
      const [balance, history] = await Promise.all([
        fetchTokenBalance(),
        fetchTokenHistory(40, 0),
      ]);
      if (get().generation !== generation) return;
      set({
        balance,
        history: history.items,
        phase: "idle",
        error: null,
      });
    } catch (err) {
      if (get().generation !== generation) return;
      const message = opts?.errorMessage?.(err);
      let error = message ?? (err instanceof Error ? err.message : "Failed to load tokens.");
      if (!message && isTokensApiError(err) && err.status === 401) {
        error = "login";
      }
      set({
        phase: "idle",
        error,
        ...(soft
          ? {}
          : {
              balance: null,
              history: [],
            }),
      });
    }
  },
}));
