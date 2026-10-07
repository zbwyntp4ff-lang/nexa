"use client";
import * as React from "react";
import {
  FolderKanban,
  MessageSquarePlus,
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
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { MODE_GRADIENT } from "@/lib/mode-theme";
import { useChatStore } from "@/store/chat-store";
import { useUiStore } from "@/store/ui-store";
export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const t = useT();
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
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground backdrop-blur-xl">
      <div className="flex items-center justify-between px-4 py-4">
        <LogoWordmark />
      </div>
      <div className="px-3">
        <Button
          onClick={handleNewChat}
          className={cn("w-full justify-start gap-2 border-none text-white shadow-lg hover:opacity-90", MODE_GRADIENT.chat)}
        >
          <MessageSquarePlus className="size-4" aria-hidden="true" />
          {t("sidebar.newChat")}
        </Button>
      </div>
      <div className="px-3 pt-3">
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("sidebar.searchChats")}
            aria-label={t("sidebar.searchChatHistory")}
            className="pl-8"
          />
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between px-4">
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
      <nav aria-label={t("sidebar.projects")} className="px-2 pt-1">
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
      <div className="mt-3 px-4">
        <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{t("sidebar.recentChats")}</span>
      </div>
      <ScrollArea className="mt-1 min-h-0 flex-1 px-2 nexa-scrollbar">
        {filtered.length === 0 ? (
          <p className="px-2 py-1.5 text-xs text-muted-foreground">
            {conversations.length === 0 ? t("sidebar.noChats") : t("sidebar.noChatsMatch")}
          </p>
        ) : (
          <ul className="space-y-0.5 pb-2" aria-label={t("sidebar.recentChats")}>
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
      </ScrollArea>
      <div className="mt-auto space-y-1 border-t border-sidebar-border p-2">
        <button
          type="button"
          onClick={() => { openSettings(); onNavigate?.(); }}
          className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Settings className="size-4" aria-hidden="true" />
          {t("sidebar.settings")}
        </button>
        <div className="flex items-center gap-2 rounded-md px-2 py-2 text-sm text-sidebar-foreground">
          <span className="flex size-7 items-center justify-center rounded-full nexa-gradient-chat text-[11px] font-semibold text-white">
            N
          </span>
          <span className="truncate">{t("sidebar.guest")}</span>
        </div>
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
