"use client";
import * as React from "react";
import {
  Compass,
  FolderKanban,
  MessageSquarePlus,
  Mic,
  MoreHorizontal,
  Pencil,
  Search,
  Settings,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { LogoWordmark } from "@/components/common/logo";
import { ModeSelector } from "@/components/chat/mode-selector";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { MODE_GRADIENT } from "@/lib/mode-theme";
import { useChatStore } from "@/store/chat-store";
import { useUiStore } from "@/store/ui-store";
export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const t = useT();
  const isPublicBeta = process.env.NEXT_PUBLIC_NEXA_PUBLIC_BETA === "true";
  const conversations = useChatStore((s) => s.conversations);
  const activeConversationId = useChatStore((s) => s.activeConversationId);
  const projects = useChatStore((s) => s.projects);
  const createConversation = useChatStore((s) => s.createConversation);
  const deleteConversation = useChatStore((s) => s.deleteConversation);
  const renameConversation = useChatStore((s) => s.renameConversation);
  const setActiveConversation = useChatStore((s) => s.setActiveConversation);
  const createProject = useChatStore((s) => s.createProject);
  const openSettings = useUiStore((s) => s.openSettings);
  const openProjects = useUiStore((s) => s.openProjects);
  const bumpPanelMotion = useUiStore((s) => s.bumpPanelMotion);
  const activeView = useUiStore((s) => s.activeView);
  const setActiveView = useUiStore((s) => s.setActiveView);
  const [query, setQuery] = React.useState("");
  const [renamingId, setRenamingId] = React.useState<string | null>(null);
  const [renameValue, setRenameValue] = React.useState("");
  const [pendingDeleteId, setPendingDeleteId] = React.useState<string | null>(null);
  const filtered = React.useMemo(() => {
    const term = query.trim().toLowerCase();
    const sorted = [...conversations].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
    if (!term) return sorted;
    return sorted.filter(
      (c) =>
        c.title.toLowerCase().includes(term) ||
        c.messages.some((m) => m.content.toLowerCase().includes(term))
    );
  }, [conversations, query]);
  function handleNewChat() {
    createConversation("chat");
    bumpPanelMotion();
    onNavigate?.();
  }
  function handleSelect(id: string) {
    setActiveConversation(id);
    onNavigate?.();
  }
  function startRename(id: string, currentTitle: string) {
    setRenamingId(id);
    setRenameValue(currentTitle);
  }
  function commitRename() {
    if (renamingId) renameConversation(renamingId, renameValue);
    setRenamingId(null);
  }
  function handleNewProject() {
    const id = createProject(t("project.untitled"));
    openProjects(id);
    onNavigate?.();
  }
  return (
    <div className="flex h-full min-h-0 flex-col bg-sidebar text-sidebar-foreground backdrop-blur-xl">
      {/* Fixed top — never covers chat history */}
      <div className="shrink-0 px-4 pt-4 pb-2">
        <LogoWordmark />
      </div>
      <div className="shrink-0 px-3 pb-2">
        <Button
          onClick={handleNewChat}
          className={cn("w-full justify-start gap-2 border-none text-white shadow-lg hover:opacity-90", MODE_GRADIENT.chat)}
        >
          <MessageSquarePlus className="size-4" aria-hidden="true" />
          {t("sidebar.newChat")}
        </Button>
      </div>
      {/* Scrollable middle: modes + projects + chat history (settings/profile stay below) */}
      <ScrollArea className="min-h-0 flex-1 px-2 nexa-scrollbar">
        <div className="px-1 pb-3">
          <p className="mb-1.5 px-1 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
            {t("sidebar.modes")}
          </p>
          <ModeSelector
            orientation="vertical"
            onSelect={() => {
              setActiveView("chat");
              onNavigate?.();
            }}
          />
          <div className={cn("mt-1.5 flex flex-col gap-0.5 rounded-lg bg-muted/40 p-1", isPublicBeta && "hidden")} role="group" aria-label={t("sidebar.views")}>
            <button
              type="button"
              aria-pressed={activeView === "omniverse"}
              onClick={() => {
                setActiveView("omniverse");
                onNavigate?.();
              }}
              className={cn(
                "flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-left text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                activeView === "omniverse"
                  ? "bg-background text-foreground shadow-sm nexa-glow-chat"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Compass className="size-4 shrink-0 text-primary" aria-hidden="true" />
              <span className="truncate">{t("omniverse.tab")}</span>
            </button>
            <button
              type="button"
              aria-pressed={activeView === "hexa"}
              onClick={() => {
                setActiveView("hexa");
                onNavigate?.();
              }}
              className={cn(
                "flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-left text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                activeView === "hexa"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Mic className="size-4 shrink-0 text-primary" aria-hidden="true" />
              <span className="truncate">HEXA</span>
            </button>
          </div>
          <div className="relative mt-3">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("sidebar.searchChats")}
              aria-label={t("sidebar.searchChatHistory")}
              className="pl-8"
            />
          </div>
          <div className={cn("mt-3 flex items-center justify-between px-1", isPublicBeta && "hidden")}>
            <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{t("sidebar.projects")}</span>
            <button
              type="button"
              onClick={handleNewProject}
              className="rounded p-1 text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label={t("sidebar.newProject")}
            >
              <FolderKanban className="size-4" aria-hidden="true" />
            </button>
          </div>
          <nav aria-label={t("sidebar.projects")} className={cn("pt-1", isPublicBeta && "hidden")}>
            {projects.length === 0 ? (
              <p className="px-2 py-1.5 text-xs text-muted-foreground">{t("sidebar.noProjects")}</p>
            ) : (
              <ul className="space-y-0.5">
                {projects.map((project) => (
                  <li key={project.id}>
                    <button
                      type="button"
                      onClick={() => { openProjects(project.id); onNavigate?.(); }}
                      className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <FolderKanban className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                      <span className="truncate">{project.name}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </nav>
          <div className="mt-3 px-1">
            <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{t("sidebar.recentChats")}</span>
          </div>
          {filtered.length === 0 ? (
            <p className="px-2 py-1.5 text-xs text-muted-foreground">
              {conversations.length === 0 ? t("sidebar.noChats") : t("sidebar.noChatsMatch")}
            </p>
          ) : (
            <ul className="mt-1 space-y-0.5 pb-2" aria-label={t("sidebar.recentChats")}>
              {filtered.map((conversation) => {
                const isActive = conversation.id === activeConversationId;
                const isRenaming = renamingId === conversation.id;
                return (
                  <li key={conversation.id} className="group relative">
                    {isRenaming ? (
                      <Input
                        autoFocus
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onBlur={commitRename}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") commitRename();
                          if (e.key === "Escape") setRenamingId(null);
                        }}
                        aria-label={t("rename.chat")}
                        className="h-8"
                      />
                    ) : (
                      <button
                        type="button"
                        onClick={() => handleSelect(conversation.id)}
                        aria-current={isActive ? "true" : undefined}
                        className={cn(
                          "flex w-full items-center gap-2 rounded-md py-1.5 pr-8 pl-2 text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                          isActive
                            ? "bg-sidebar-accent text-sidebar-accent-foreground"
                            : "text-sidebar-foreground hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground"
                        )}
                      >
                        <span className="truncate">{conversation.title}</span>
                      </button>
                    )}
                    {!isRenaming && (
                      <DropdownMenu>
                        <DropdownMenuTrigger
                          render={
                            <button
                              type="button"
                              className="absolute top-1/2 right-1 -translate-y-1/2 rounded p-1 text-muted-foreground opacity-0 hover:bg-sidebar-accent focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring group-hover:opacity-100"
                              aria-label={`More actions for ${conversation.title}`}
                            >
                              <MoreHorizontal className="size-4" aria-hidden="true" />
                            </button>
                          }
                        />
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => startRename(conversation.id, conversation.title)}>
                            <Pencil className="size-4" aria-hidden="true" />
                            {t("chat.edit")}
                          </DropdownMenuItem>
                          <DropdownMenuItem variant="destructive" onClick={() => setPendingDeleteId(conversation.id)}>
                            <Trash2 className="size-4" aria-hidden="true" />
                            {t("delete.confirm")}
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </ScrollArea>
      {/* Fixed footer — never overlays chat list */}
      <div className="z-10 shrink-0 space-y-1 border-t border-sidebar-border bg-sidebar p-2">
        <button
          type="button"
          onClick={() => { openSettings(); onNavigate?.(); }}
          className={cn("flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", isPublicBeta && "hidden")}
        >
          <Settings className="size-4" aria-hidden="true" />
          {t("sidebar.settings")}
        </button>
        <button
          type="button"
          onClick={() => { openSettings("personalization"); onNavigate?.(); }}
          className={cn("flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", isPublicBeta && "hidden")}
        >
          <span className="flex size-7 items-center justify-center rounded-full nexa-gradient-chat text-[11px] font-semibold text-white">
            N
          </span>
          <span className="truncate">{t("sidebar.guest")}</span>
        </button>
      </div>
      <AlertDialog open={pendingDeleteId !== null} onOpenChange={(open) => !open && setPendingDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("delete.title")}</AlertDialogTitle>
            <AlertDialogDescription>{t("delete.desc")}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("chat.cancel")}</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (pendingDeleteId) deleteConversation(pendingDeleteId);
                setPendingDeleteId(null);
              }}
            >
              {t("delete.confirm")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
