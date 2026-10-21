import type { ClipboardEvent } from "react";
import { normalizeEmailInput } from "@/lib/normalize-email";

/** Apply clipboard text into a controlled input (Electron / Base UI safe). */
export function applyPasteToControlledInput(
  e: ClipboardEvent<HTMLInputElement>,
  apply: (value: string) => void,
  options?: { normalizeEmail?: boolean },
): void {
  let text = e.clipboardData.getData("text");
  if (text == null) return;
  e.preventDefault();
  if (options?.normalizeEmail) {
    text = normalizeEmailInput(text);
    apply(text);
    const el = e.currentTarget;
    requestAnimationFrame(() => {
      try {
        const caret = text.length;
        el.setSelectionRange(caret, caret);
      } catch {
        /* ignore */
      }
    });
    return;
  }
  const el = e.currentTarget;
  const start = el.selectionStart ?? el.value.length;
  const end = el.selectionEnd ?? el.value.length;
  const next = `${el.value.slice(0, start)}${text}${el.value.slice(end)}`;
  apply(next);
  const caret = start + text.length;
  requestAnimationFrame(() => {
    try {
      el.setSelectionRange(caret, caret);
    } catch {
      /* ignore */
    }
  });
}
