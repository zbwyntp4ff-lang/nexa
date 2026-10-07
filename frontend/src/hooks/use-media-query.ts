"use client";
import * as React from "react";
function subscribe(query: string, callback: () => void) {
  const mediaQueryList = window.matchMedia(query);
  mediaQueryList.addEventListener("change", callback);
  return () => mediaQueryList.removeEventListener("change", callback);
}
/** SSR-safe media query hook, backed by useSyncExternalStore (no effect needed). */
export function useMediaQuery(query: string): boolean {
  return React.useSyncExternalStore(
    (callback) => subscribe(query, callback),
    () => window.matchMedia(query).matches,
    () => false
  );
}
export const DESKTOP_QUERY = "(min-width: 1024px)";
