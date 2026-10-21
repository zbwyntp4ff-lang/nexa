"use client";
import * as React from "react";
import { useI18nStore, type Language } from "./i18n-store";
import { en } from "./translations-en";
import { ru } from "./translations-ru";

const DICTS: Record<Language, Record<string, string>> = { en, ru };

export type TranslateFn = (key: string, params?: Record<string, string | number>) => string;

/** Stable translator — identity changes only when language changes (avoids effect loops). */
export function useT(): TranslateFn {
  const language = useI18nStore((s) => s.language);
  return React.useCallback<TranslateFn>(
    (key, params) => {
      const dict = DICTS[language] ?? en;
      let str = dict[key] ?? en[key] ?? key;
      if (params) {
        for (const [k, v] of Object.entries(params)) {
          str = str.replace(`{${k}}`, String(v));
        }
      }
      return str;
    },
    [language],
  );
}

export { type Language };
