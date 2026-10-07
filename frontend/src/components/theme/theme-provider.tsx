"use client";
import * as React from "react";
import { ThemeProvider as NextThemesProvider } from "next-themes";
/**
 * Wraps next-themes with NEXA's defaults: three explicit options
 * (light/dark/system), persisted to localStorage under `nexa-theme`, applied
 * via a `.dark` class on <html> (matches the CSS in globals.css).
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem
      storageKey="nexa-theme"
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  );
}
