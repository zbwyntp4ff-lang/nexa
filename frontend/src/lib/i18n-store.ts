"use client";
import { create } from "zustand";
import { persist } from "zustand/middleware";
export type Language = "en" | "ru";
interface I18nStore {
  language: Language;
  setLanguage: (lang: Language) => void;
  toggleLanguage: () => void;
}
export const useI18nStore = create<I18nStore>()(
  persist(
    (set, get) => ({
      language: "en",
      setLanguage: (lang) => set({ language: lang }),
      toggleLanguage: () => set({ language: get().language === "en" ? "ru" : "en" }),
    }),
    { name: "nexa-i18n" }
  )
);
