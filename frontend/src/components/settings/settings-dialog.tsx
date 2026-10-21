"use client";

import * as React from "react";
import {
  BookOpen,
  Bot,
  Brain,
  Coins,
  CreditCard,
  GraduationCap,
  Info,
  Palette,
  Puzzle,
  Settings as SettingsIcon,
  Shield,
  Sparkles,
  Wrench,
} from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { useUiStore, type SettingsSection } from "@/store/ui-store";
import { AboutSection } from "./sections/about-section";
import { AppearanceSection } from "./sections/appearance-section";
import { BillingSection } from "./sections/billing-section";
import { GeneralSection } from "./sections/general-section";
import { KnowledgeSection } from "./sections/knowledge-section";
import { LearningSection } from "./sections/learning-section";
import { MemorySection } from "./sections/memory-section";
import { ModelsSection } from "./sections/models-section";
import { PersonalizationSection } from "./sections/personalization-section";
import { PluginsSection } from "./sections/plugins-section";
import { PrivacySection } from "./sections/privacy-section";
import { TokensSection } from "./sections/tokens-section";
import { ToolsSection } from "./sections/tools-section";

/** Stable map — must not be recreated inside the dialog render (remount risk). */
const SECTION_COMPONENTS: Record<SettingsSection, React.ComponentType> = {
  general: GeneralSection,
  appearance: AppearanceSection,
  models: ModelsSection,
  billing: BillingSection,
  tokens: TokensSection,
  personalization: PersonalizationSection,
  memory: MemorySection,
  knowledge: KnowledgeSection,
  learning: LearningSection,
  privacy: PrivacySection,
  tools: ToolsSection,
  plugins: PluginsSection,
  about: AboutSection,
};

const NAV_IDS: SettingsSection[] = [
  "general",
  "personalization",
  "tokens",
  "appearance",
  "models",
  "billing",
  "memory",
  "knowledge",
  "learning",
  "privacy",
  "tools",
  "plugins",
  "about",
];

const NAV_ICONS: Record<SettingsSection, typeof SettingsIcon> = {
  general: SettingsIcon,
  personalization: Sparkles,
  tokens: Coins,
  appearance: Palette,
  models: Bot,
  billing: CreditCard,
  memory: Brain,
  knowledge: BookOpen,
  learning: GraduationCap,
  privacy: Shield,
  tools: Wrench,
  plugins: Puzzle,
  about: Info,
};

export function SettingsDialog() {
  const t = useT();
  const open = useUiStore((s) => s.settingsOpen);
  const closeSettings = useUiStore((s) => s.closeSettings);
  const section = useUiStore((s) => s.settingsSection);
  const openSettings = useUiStore((s) => s.openSettings);
  /** Keep visited panes mounted so Tokens (and others) do not remount/flicker. */
  const [visited, setVisited] = React.useState<SettingsSection[]>(["general"]);

  React.useEffect(() => {
    setVisited((prev) => (prev.includes(section) ? prev : [...prev, section]));
  }, [section]);

  const navLabels: Record<SettingsSection, string> = {
    general: t("settings.general"),
    personalization: t("settings.personalization"),
    tokens: t("settings.tokens"),
    appearance: t("settings.appearance"),
    models: t("settings.models"),
    billing: t("settings.billing"),
    memory: t("settings.memory"),
    knowledge: t("settings.knowledge"),
    learning: t("settings.learning"),
    privacy: t("settings.privacy"),
    tools: t("settings.tools"),
    plugins: t("settings.plugins"),
    about: t("settings.about"),
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (next) openSettings(section);
        else closeSettings();
      }}
    >
      <DialogContent
        className={cn(
          "top-0 left-0 flex h-dvh max-h-dvh w-screen max-w-none translate-x-0 translate-y-0 flex-col gap-0 overflow-hidden rounded-none p-0 ring-0 sm:max-w-none sm:flex-row",
          "data-open:zoom-in-100 data-closed:zoom-out-100",
        )}
      >
        <DialogHeader className="sr-only">
          <DialogTitle>{t("settings.title")}</DialogTitle>
        </DialogHeader>
        <nav
          aria-label={t("settings.sections")}
          className="flex shrink-0 gap-1 overflow-x-auto border-b border-border bg-muted/30 p-3 sm:w-60 sm:flex-col sm:overflow-y-auto sm:overflow-x-visible sm:border-r sm:border-b-0"
        >
          <p className="mb-1 hidden px-2.5 pt-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase sm:block">
            {t("settings.title")}
          </p>
          {NAV_IDS.map((id) => {
            const Icon = NAV_ICONS[id];
            return (
              <button
                key={id}
                type="button"
                onClick={() => openSettings(id)}
                aria-current={section === id ? "true" : undefined}
                className={cn(
                  "flex shrink-0 items-center gap-2 rounded-md px-2.5 py-2.5 text-left text-sm font-medium whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  section === id
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <Icon className="size-4" aria-hidden="true" />
                {navLabels[id]}
              </button>
            );
          })}
        </nav>
        <div className="min-h-0 flex-1 overflow-y-auto p-6 sm:p-8 nexa-scrollbar">
          <div className="relative mx-auto w-full max-w-3xl">
            {visited.map((id) => {
              const Comp = SECTION_COMPONENTS[id];
              const active = id === section;
              return (
                <div
                  key={id}
                  hidden={!active}
                  className={cn(!active && "hidden")}
                  aria-hidden={!active}
                >
                  <Comp />
                </div>
              );
            })}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
