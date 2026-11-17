"use client";

import * as React from "react";
import { ChatPanel } from "@/components/chat/chat-panel";
import { BetaUsage } from "@/components/beta/beta-usage";
import { HexaVoicePanel } from "@/components/hexa/hexa-voice-panel";
import { Header } from "@/components/layout/header";
import { PlanPromoDialog } from "@/components/layout/plan-promo-dialog";
import { RightDock } from "@/components/layout/right-dock";
import { DesktopSidebar } from "@/components/layout/sidebar/sidebar";
import { MobileSidebar } from "@/components/layout/sidebar/mobile-sidebar";
import { StorageModeBanner } from "@/components/layout/storage-mode-banner";
import { GameCreatorPanel } from "@/components/game-creator/game-creator-panel";
import { OmniversePanel } from "@/components/omniverse/omniverse-panel";
import { SettingsDialog } from "@/components/settings/settings-dialog";
import { ProjectPanel } from "@/components/projects/project-panel";
import { WorkflowPanel } from "@/components/workflows/workflow-panel";
import { useBackendHealth } from "@/hooks/use-backend-health";
import { useUiStore } from "@/store/ui-store";

export function AppShell() {
  useBackendHealth();
  const activeView = useUiStore((s) => s.activeView);
  const openSettings = useUiStore((s) => s.openSettings);
  const isOmni = activeView === "omniverse";
  const isHexa = activeView === "hexa";
  const isChat = activeView === "chat";
  const isPublicBeta = process.env.NEXT_PUBLIC_NEXA_PUBLIC_BETA === "true";

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("settings") === "billing") {
      openSettings("billing");
    }
  }, [openSettings]);

  return (
    <div className="nexa-chat-atmosphere flex h-dvh w-full overflow-hidden text-foreground">
      <DesktopSidebar />
      <MobileSidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <StorageModeBanner />
        {isPublicBeta && <BetaUsage />}
        {!isHexa && <Header />}
        <main className="min-h-0 flex-1">
          {isHexa ? (
            <HexaVoicePanel />
          ) : isOmni ? (
            <OmniversePanel />
          ) : (
            <ChatPanel />
          )}
        </main>
      </div>
      {isChat && <RightDock />}
      <SettingsDialog />
      <PlanPromoDialog />
      <ProjectPanel />
      <GameCreatorPanel />
      <WorkflowPanel />
    </div>
  );
}
