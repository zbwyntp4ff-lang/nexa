"use client";
import * as React from "react";
import { ChatPanel } from "@/components/chat/chat-panel";
import { HexaVoicePanel } from "@/components/hexa/hexa-voice-panel";
import { Header } from "@/components/layout/header";
import { RightDock } from "@/components/layout/right-dock";
import { DesktopSidebar } from "@/components/layout/sidebar/sidebar";
import { MobileSidebar } from "@/components/layout/sidebar/mobile-sidebar";
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

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("settings") === "billing") {
      openSettings("billing");
    }
  }, [openSettings]);
  if (isHexa) {
    return (
      <div className="flex h-dvh w-full overflow-hidden">
        <HexaVoicePanel />
        <SettingsDialog />
      </div>
    );
  }
  return (
    <div className="nexa-chat-atmosphere flex h-dvh w-full overflow-hidden text-foreground">
      {!isOmni && (
        <>
          <DesktopSidebar />
          <MobileSidebar />
        </>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <main className="min-h-0 flex-1">{isOmni ? <OmniversePanel /> : <ChatPanel />}</main>
      </div>
      {!isOmni && <RightDock />}
      <SettingsDialog />
      <ProjectPanel />
      <WorkflowPanel />
    </div>
  );
}
