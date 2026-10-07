/** Basic built-in capability toggles (Part 11 "Plugins" tab).
 * Each plugin maps to real, already-functional NEXA capabilities - toggling
 * one off actually disables it (Agent tool calls get refused server-side;
 * Research/Create/Vision modes are grayed out client-side), it's never a
 * cosmetic-only switch.
 */
import type { LucideIcon } from "lucide-react";
import { Calculator, Compass, Eye, FolderOpen, Image as ImageIcon } from "lucide-react";
import type { AppMode } from "./types";
export type PluginId =
  | "web_search"
  | "calculator"
  | "file_system"
  | "image_generation"
  | "vision";
export interface PluginDefinition {
  id: PluginId;
  icon: LucideIcon;
  /** Agent tool names this plugin's toggle refuses when turned off. */
  toolNames: string[];
  /** The chat mode this plugin fully gates when turned off, if any. */
  gatesMode?: AppMode;
  /** Show a quick toggle on the outer sidebar (not only inside Settings). */
  outerSidebar?: boolean;
}
export const PLUGINS: PluginDefinition[] = [
  { id: "web_search", icon: Compass, toolNames: ["web_research"], gatesMode: "research", outerSidebar: true },
  { id: "calculator", icon: Calculator, toolNames: ["calculator"] },
  {
    id: "file_system",
    icon: FolderOpen,
    toolNames: ["file_read", "file_write", "file_create", "file_rename", "directory_list", "directory_create"],
  },
  { id: "image_generation", icon: ImageIcon, toolNames: [], gatesMode: "create" },
  { id: "vision", icon: Eye, toolNames: [], gatesMode: "vision" },
];
export const OUTER_SIDEBAR_PLUGINS = PLUGINS.filter((p) => p.outerSidebar);
export const DEFAULT_PLUGIN_STATE: Record<PluginId, boolean> = {
  web_search: true,
  calculator: true,
  file_system: true,
  image_generation: true,
  vision: true,
};
/** The plugin that must be on for `mode` to be usable, if the mode is plugin-gated. */
export function pluginGatingMode(mode: AppMode): PluginId | null {
  return PLUGINS.find((p) => p.gatesMode === mode)?.id ?? null;
}
/** Agent tool names to refuse for this run, given the current plugin toggles. */
export function disabledToolNames(enabled: Record<PluginId, boolean>): string[] {
  return PLUGINS.filter((p) => !enabled[p.id]).flatMap((p) => p.toolNames);
}
