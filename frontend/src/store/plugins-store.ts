"use client";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import { DEFAULT_PLUGIN_STATE, type PluginId } from "@/lib/plugins";
interface PluginsState {
  enabled: Record<PluginId, boolean>;
  setPlugin: (id: PluginId, value: boolean) => void;
}
export const usePluginsStore = create<PluginsState>()(
  persist(
    (set) => ({
      enabled: DEFAULT_PLUGIN_STATE,
      setPlugin: (id, value) =>
        set((state) => ({ enabled: { ...state.enabled, [id]: value } })),
    }),
    {
      name: "nexa-plugins-store",
      version: 2,
      // v1 shipped Create/Vision off for a pre-release pass; turn them back on.
      migrate: (persisted) => {
        const state = (persisted ?? {}) as Partial<PluginsState>;
        const enabled = { ...DEFAULT_PLUGIN_STATE, ...(state.enabled ?? {}) };
        enabled.image_generation = true;
        enabled.vision = true;
        return { ...state, enabled };
      },
      merge: (persisted, current) => {
        const fromStorage = (persisted as Partial<PluginsState> | undefined)?.enabled;
        return {
          ...current,
          ...(persisted as object),
          enabled: { ...DEFAULT_PLUGIN_STATE, ...fromStorage },
        };
      },
    }
  )
);
