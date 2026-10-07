"use client";
import { BookOpen, Bot, Brain, CreditCard, Info, Palette, Puzzle, Settings as SettingsIcon, Shield, Wrench } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { useUiStore, type SettingsSection } from "@/store/ui-store";
import { AboutSection } from "./sections/about-section";
import { AppearanceSection } from "./sections/appearance-section";
import { BillingSection } from "./sections/billing-section";
import { GeneralSection } from "./sections/general-section";
import { KnowledgeSection } from "./sections/knowledge-section";
import { MemorySection } from "./sections/memory-section";
import { ModelsSection } from "./sections/models-section";
import { PluginsSection } from "./sections/plugins-section";
import { PrivacySection } from "./sections/privacy-section";
import { ToolsSection } from "./sections/tools-section";
export function SettingsDialog() {
  const t = useT();
  const open = useUiStore((s) => s.settingsOpen);
  const closeSettings = useUiStore((s) => s.closeSettings);
  const section = useUiStore((s) => s.settingsSection);
  const openSettings = useUiStore((s) => s.openSettings);
  const NAV: { id: SettingsSection; label: string; icon: typeof SettingsIcon }[] = [
    { id: "general", label: t("settings.general"), icon: SettingsIcon },
    { id: "appearance", label: t("settings.appearance"), icon: Palette },
    { id: "models", label: t("settings.models"), icon: Bot },
    { id: "billing", label: t("settings.billing"), icon: CreditCard },
    { id: "memory", label: t("settings.memory"), icon: Brain },
    { id: "knowledge", label: t("settings.knowledge"), icon: BookOpen },
    { id: "privacy", label: t("settings.privacy"), icon: Shield },
    { id: "tools", label: t("settings.tools"), icon: Wrench },
    { id: "plugins", label: t("settings.plugins"), icon: Puzzle },
    { id: "about", label: t("settings.about"), icon: Info },
  ];
  const SECTION_COMPONENTS: Record<SettingsSection, React.ComponentType> = {
    general: GeneralSection, appearance: AppearanceSection, models: ModelsSection,
    billing: BillingSection,
    memory: MemorySection, knowledge: KnowledgeSection, privacy: PrivacySection, tools: ToolsSection,
    plugins: PluginsSection, about: AboutSection,
  };
  const ActiveSection = SECTION_COMPONENTS[section];
  return (
    <Dialog open={open} onOpenChange={(next) => (next ? openSettings(section) : closeSettings())}>
      <DialogContent
        className={cn(
          "top-0 left-0 flex h-dvh max-h-dvh w-screen max-w-none translate-x-0 translate-y-0 flex-col gap-0 overflow-hidden rounded-none p-0 ring-0 sm:max-w-none sm:flex-row",
          "data-open:zoom-in-100 data-closed:zoom-out-100"
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
          {NAV.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => openSettings(id)}
              aria-current={section === id ? "true" : undefined}
              className={cn(
                "flex shrink-0 items-center gap-2 rounded-md px-2.5 py-2.5 text-left text-sm font-medium whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                section === id ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              <Icon className="size-4" aria-hidden="true" />
              {label}
            </button>
          ))}
        </nav>
        <div className="min-h-0 flex-1 overflow-y-auto p-6 sm:p-8 nexa-scrollbar">
          <div className="mx-auto w-full max-w-3xl">
            <ActiveSection />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
