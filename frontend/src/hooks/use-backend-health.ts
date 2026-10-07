"use client";
import * as React from "react";
import { getHealth } from "@/lib/api";
import { useUiStore } from "@/store/ui-store";
const POLL_INTERVAL_MS = 15_000;
const IDLE_STATUSES = new Set(["online", "offline", "error"]);
/**
 * Polls GET /health so the status indicator reflects the *real* backend
 * reachability, not a hard-coded "Online". Never overrides a transient
 * status (thinking/using_tool/researching/generating) that's already in
 * progress from a real in-flight request.
 */
export function useBackendHealth() {
  React.useEffect(() => {
    let cancelled = false;
    async function check() {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 5000);
      try {
        await getHealth(controller.signal);
        if (cancelled) return;
        const current = useUiStore.getState().status;
        if (IDLE_STATUSES.has(current)) useUiStore.getState().setStatus("online");
      } catch {
        if (cancelled) return;
        const current = useUiStore.getState().status;
        if (IDLE_STATUSES.has(current)) useUiStore.getState().setStatus("offline");
      } finally {
        clearTimeout(timeout);
      }
    }
    check();
    const interval = setInterval(check, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);
}
