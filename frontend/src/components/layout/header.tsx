"use client";
import { Compass, Menu, MessageSquarePlus, Mic, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ModeSelector } from "@/components/chat/mode-selector";
import { StatusIndicator } from "@/components/chat/status-indicator";
import { LogoWordmark } from "@/components/common/logo";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { useChatStore } from "@/store/chat-store";
import { useUiStore } from "@/store/ui-store";

export function Header() {
  const t = useT();
  const collapsed = useUiStore((s) => s.desktopSidebarCollapsed);
  const toggleDesktopSidebar = useUiStore((s) => s.toggleDesktopSidebar);
  const setMobileDrawerOpen = useUiStore((s) => s.setMobileDrawerOpen);
  const createConversation = useChatStore((s) => s.createConversation);
  const activeView = useUiStore((s) => s.activeView);
  const setActiveView = useUiStore((s) => s.setActiveView);
  const isOmni = activeView === "omniverse";
  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border bg-background/80 px-3 backdrop-blur-md">
      {!isOmni && (
        <>
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            aria-label={t("header.openSidebar")}
            onClick={() => setMobileDrawerOpen(true)}
          >
            <Menu className="size-5" aria-hidden="true" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="hidden lg:inline-flex"
            aria-label={collapsed ? t("header.expandSidebar") : t("header.collapseSidebar")}
            aria-pressed={collapsed}
            onClick={toggleDesktopSidebar}
          >
            {collapsed ? (
              <PanelLeftOpen className="size-5" aria-hidden="true" />
            ) : (
              <PanelLeftClose className="size-5" aria-hidden="true" />
            )}
          </Button>
          {collapsed && (
            <div className="hidden items-center gap-3 lg:flex">
              <LogoWordmark />
              <Button
                variant="ghost"
                size="icon"
                aria-label={t("header.newChat")}
                onClick={() => createConversation("chat")}
              >
                <MessageSquarePlus className="size-5" aria-hidden="true" />
              </Button>
            </div>
          )}
        </>
      )}
      {isOmni && <LogoWordmark className="shrink-0" />}
      <div className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto">
        {!isOmni && <ModeSelector />}
        <button
          type="button"
          onClick={() => setActiveView(isOmni ? "chat" : "omniverse")}
          aria-pressed={isOmni}
          className={cn(
            "flex shrink-0 items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            isOmni
              ? "border-primary/50 bg-primary/15 text-foreground nexa-glow-chat"
              : "border-transparent bg-muted/60 text-muted-foreground hover:text-foreground"
          )}
        >
          <Compass className="size-4 text-primary" aria-hidden="true" />
          <span className="hidden sm:inline">{t("omniverse.tab")}</span>
          <span className="sm:hidden">OMNI</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveView("hexa")}
          className="flex shrink-0 items-center gap-1.5 rounded-lg border border-transparent bg-muted/60 px-2.5 py-1.5 text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Mic className="size-4 text-primary" aria-hidden="true" />
          <span className="hidden sm:inline">HEXA</span>
        </button>
      </div>
      <StatusIndicator className="hidden shrink-0 sm:flex" />
    </header>
  );
}
