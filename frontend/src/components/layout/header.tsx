"use client";

import { Menu, MessageSquarePlus, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusIndicator } from "@/components/chat/status-indicator";
import { LogoWordmark } from "@/components/common/logo";
import { useT } from "@/lib/i18n";
import { useChatStore } from "@/store/chat-store";
import { useUiStore } from "@/store/ui-store";

/** Top bar — all mode/view tabs live in the left sidebar. */
export function Header() {
  const t = useT();
  const collapsed = useUiStore((s) => s.desktopSidebarCollapsed);
  const toggleDesktopSidebar = useUiStore((s) => s.toggleDesktopSidebar);
  const setMobileDrawerOpen = useUiStore((s) => s.setMobileDrawerOpen);
  const createConversation = useChatStore((s) => s.createConversation);
  const bumpPanelMotion = useUiStore((s) => s.bumpPanelMotion);
  const setActiveView = useUiStore((s) => s.setActiveView);
  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border bg-background/80 px-3 backdrop-blur-md">
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
            onClick={() => {
              setActiveView("chat");
              createConversation("chat");
              bumpPanelMotion();
            }}
          >
            <MessageSquarePlus className="size-5" aria-hidden="true" />
          </Button>
        </div>
      )}
      <div className="min-w-0 flex-1" aria-hidden="true" />
      <StatusIndicator className="hidden shrink-0 sm:flex" />
    </header>
  );
}
