/**
 * Per-mode visual identity (Part 11). Each `AppMode` gets its own accent
 * gradient/color so chat, agent, code, research, create and vision all
 * *look* different, not just behave differently.
 *
 * Tailwind v4 purges classes it cannot find as a literal substring during
 * its content scan, so every class name below is written out in full (never
 * built with template-string interpolation) even though it lives in a
 * lookup object - see `@utility nexa-gradient-*` / `nexa-text-*` in
 * `globals.css` for the underlying CSS.
 */
import type { AppMode } from "./types";
export const MODE_GRADIENT: Record<AppMode, string> = {
  chat: "nexa-gradient-chat",
  agent: "nexa-gradient-agent",
  code: "nexa-gradient-code",
  research: "nexa-gradient-research",
  create: "nexa-gradient-create",
  vision: "nexa-gradient-vision",
};
export const MODE_TEXT_ACCENT: Record<AppMode, string> = {
  chat: "nexa-text-chat",
  agent: "nexa-text-agent",
  code: "nexa-text-code",
  research: "nexa-text-research",
  create: "nexa-text-create",
  vision: "nexa-text-vision",
};
export const MODE_GLOW: Record<AppMode, string> = {
  chat: "nexa-glow-chat",
  agent: "nexa-glow-agent",
  code: "nexa-glow-code",
  research: "nexa-glow-research",
  create: "nexa-glow-create",
  vision: "nexa-glow-vision",
};
