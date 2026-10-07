"use client";
import { useI18nStore, type Language } from "./i18n-store";
import { en } from "./translations-en";
import { ru } from "./translations-ru";
const DICTS: Record<Language, Record<string, string>> = { en, ru };
export function useT() {
  const language = useI18nStore((s) => s.language);
  const dict = DICTS[language] ?? en;
  return (key: string, params?: Record<string, string | number>) => {
    let str = dict[key] ?? en[key] ?? key;
    if (params) for (const [k, v] of Object.entries(params)) str = str.replace(`{${k}}`, String(v));
    return str;
  };
}
export { type Language };
