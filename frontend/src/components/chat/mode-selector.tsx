"use client";

import { Fragment, useLayoutEffect, useRef, useState } from "react";
import { Bot, Code2, Compass, Lock, MessageCircle, Sparkles, Eye } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { AVAILABLE_MODES, MODES, type AppMode } from "@/lib/types";
import { MODE_GLOW, MODE_TEXT_ACCENT } from "@/lib/mode-theme";
import { pluginGatingMode } from "@/lib/plugins";
import { useT } from "@/lib/i18n";
import { useChatStore } from "@/store/chat-store";
import { usePluginsStore } from "@/store/plugins-store";
import { useUiStore } from "@/store/ui-store";

const ICONS: Record<AppMode, typeof MessageCircle> = {
  chat: MessageCircle,
  agent: Bot,
  code: Code2,
  research: Compass,
  create: Sparkles,
  vision: Eye,
};

type Orientation = "horizontal" | "vertical";

/**
 * Mode tabs. Selecting a mode always opens a **new** conversation for that
 * mode (does not continue the previous thread).
 */
export function ModeSelector({
  orientation = "vertical",
  onSelect,
  className,
}: {
  orientation?: Orientation;
  onSelect?: () => void;
  className?: string;
}) {
  const t = useT();
  const conversations = useChatStore((s) => s.conversations);
  const activeConversationId = useChatStore((s) => s.activeConversationId);
  const createConversation = useChatStore((s) => s.createConversation);
  const pendingMode = useUiStore((s) => s.pendingMode);
  const setPendingMode = useUiStore((s) => s.setPendingMode);
  const bumpPanelMotion = useUiStore((s) => s.bumpPanelMotion);
  const enabledPlugins = usePluginsStore((s) => s.enabled);
  const activeConversation = conversations.find((c) => c.id === activeConversationId);
  const currentMode = activeConversation?.mode ?? pendingMode;
  const listRef = useRef<HTMLDivElement | null>(null);
  const tabRefs = useRef<Partial<Record<AppMode, HTMLButtonElement | null>>>({});
  const [indicator, setIndicator] = useState<{
    left: number;
    top: number;
    width: number;
    height: number;
  } | null>(null);
  const vertical = orientation === "vertical";

  useLayoutEffect(() => {
    const tab = tabRefs.current[currentMode];
    const list = listRef.current;
    if (!tab || !list) return;
    const tabRect = tab.getBoundingClientRect();
    const listRect = list.getBoundingClientRect();
    setIndicator({
      left: tabRect.left - listRect.left,
      top: tabRect.top - listRect.top,
      width: tabRect.width,
      height: tabRect.height,
    });
  }, [currentMode, vertical]);

  function selectMode(mode: AppMode) {
    const gatingPlugin = pluginGatingMode(mode);
    const pluginOff = gatingPlugin ? !enabledPlugins[gatingPlugin] : false;
    const isAvailable = AVAILABLE_MODES.has(mode) && !pluginOff;
    if (!isAvailable) return;

    // New empty chat for this mode — never continue the previous thread.
    setPendingMode(mode);
    createConversation(mode);
    bumpPanelMotion();
    onSelect?.();
  }

  return (
    <div
      ref={listRef}
      role="tablist"
      aria-label={t("sidebar.modes")}
      aria-orientation={vertical ? "vertical" : "horizontal"}
      className={cn(
        "relative",
        vertical
          ? "flex w-full flex-col gap-0.5 rounded-lg bg-muted/40 p-1"
          : "flex w-max items-center gap-1 rounded-lg bg-muted/60 p-1",
        className,
      )}
    >
      {indicator && (
        <span
          aria-hidden="true"
          className={cn(
            "pointer-events-none absolute rounded-md bg-background transition-[left,top,width,height,box-shadow] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]",
            MODE_GLOW[currentMode],
          )}
          style={{
            left: indicator.left,
            top: indicator.top,
            width: indicator.width,
            height: indicator.height,
          }}
        />
      )}
      {MODES.map((mode) => {
        const Icon = ICONS[mode.id];
        const isActive = currentMode === mode.id;
        const gatingPlugin = pluginGatingMode(mode.id);
        const pluginOff = gatingPlugin ? !enabledPlugins[gatingPlugin] : false;
        const isAvailable = AVAILABLE_MODES.has(mode.id) && !pluginOff;
        const button = (
          <button
            ref={(el) => {
              tabRefs.current[mode.id] = el;
            }}
            type="button"
            role="tab"
            aria-selected={isActive}
            aria-label={
              isAvailable
                ? t(`mode.${mode.id}`)
                : `${t(`mode.${mode.id}`)} (${pluginOff ? t("plugins.modeDisabled") : t("mode.comingSoon")})`
            }
            onClick={() => selectMode(mode.id)}
            className={cn(
              "relative z-10 flex items-center gap-2 rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              vertical ? "w-full px-2.5 py-1.5" : "gap-1.5 px-2.5 py-1.5 whitespace-nowrap",
              isActive ? "text-foreground" : "text-muted-foreground hover:text-foreground",
              !isAvailable && "opacity-70",
            )}
          >
            <Icon className={cn("size-4 shrink-0", isActive && MODE_TEXT_ACCENT[mode.id])} aria-hidden="true" />
            <span className="truncate">{t(`mode.${mode.id}`)}</span>
            {pluginOff ? (
              <Lock className="ml-auto size-3 shrink-0" aria-hidden="true" />
            ) : (
              !isAvailable && (
                <span className="ml-auto rounded-full bg-muted-foreground/15 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-muted-foreground uppercase">
                  {t("mode.soon")}
                </span>
              )
            )}
          </button>
        );
        if (isAvailable) return <Fragment key={mode.id}>{button}</Fragment>;
        return (
          <Tooltip key={mode.id}>
            <TooltipTrigger render={button} />
            <TooltipContent>
              {t(`mode.${mode.id}.desc`)} — {pluginOff ? t("plugins.modeDisabled") : t("mode.comingSoon")}.
            </TooltipContent>
          </Tooltip>
        );
      })}
    </div>
  );
}
