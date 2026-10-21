"use client";
import * as React from "react";
import { FileText, Loader2, MessageSquare, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, createMemory, listMemory, type MemoryItemApi } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { useChatStore } from "@/store/chat-store";
import { useUiStore } from "@/store/ui-store";
export function ProjectPanel() {
  const t = useT();
  const open = useUiStore((s) => s.projectsOpen);
  const closeProjects = useUiStore((s) => s.closeProjects);
  const activeProjectId = useUiStore((s) => s.activeProjectId);
  const projects = useChatStore((s) => s.projects);
  const conversations = useChatStore((s) => s.conversations);
  const updateProject = useChatStore((s) => s.updateProject);
  const deleteProject = useChatStore((s) => s.deleteProject);
  const addFileToProject = useChatStore((s) => s.addFileToProject);
  const createConversation = useChatStore((s) => s.createConversation);
  const setActiveConversation = useChatStore((s) => s.setActiveConversation);
  const project = projects.find((p) => p.id === activeProjectId);
  const projectConversations = conversations.filter((c) => c.projectId === activeProjectId);
  const [name, setName] = React.useState(project?.name ?? "");
  const [instructions, setInstructions] = React.useState(project?.instructions ?? "");
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);
  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setName(project?.name ?? "");
    setInstructions(project?.instructions ?? "");
  }, [project?.id, project?.name, project?.instructions]);
  if (!project) return null;
  function handleNameBlur() {
    if (project && name.trim() && name.trim() !== project.name) updateProject(project.id, { name: name.trim() });
  }
  function handleInstructionsBlur() {
    if (project) updateProject(project.id, { instructions });
  }
  function handleNewChat() {
    const id = createConversation("chat", project!.id);
    setActiveConversation(id);
    closeProjects();
  }
  return (
    <Dialog open={open} onOpenChange={(next) => !next && closeProjects()}>
      <DialogContent className="flex h-[32rem] max-h-[85vh] w-full max-w-xl flex-col gap-3 overflow-hidden">
        <DialogHeader>
          <DialogTitle>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              onBlur={handleNameBlur}
              aria-label={t("rename.project")}
              className="border-none px-0 text-lg font-semibold shadow-none focus-visible:ring-0"
            />
          </DialogTitle>
        </DialogHeader>
        <Tabs defaultValue="conversations" className="flex min-h-0 flex-1 flex-col">
          <TabsList>
            <TabsTrigger value="conversations">{t("project.conversations")}</TabsTrigger>
            <TabsTrigger value="files">{t("project.files")}</TabsTrigger>
            <TabsTrigger value="memory">{t("project.memory")}</TabsTrigger>
            <TabsTrigger value="instructions">{t("project.instructions")}</TabsTrigger>
            <TabsTrigger value="personalization">{t("project.personalization")}</TabsTrigger>
          </TabsList>
          <TabsContent value="conversations" className="min-h-0 flex-1 overflow-y-auto nexa-scrollbar">
            <Button size="sm" variant="outline" className="mb-2" onClick={handleNewChat}>
              <Plus className="size-4" aria-hidden="true" /> {t("project.newChat")}
            </Button>
            {projectConversations.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("project.noConversations")}</p>
            ) : (
              <ul className="space-y-1">
                {projectConversations.map((c) => (
                  <li key={c.id}>
                    <button
                      type="button"
                      onClick={() => { setActiveConversation(c.id); closeProjects(); }}
                      className="flex w-full items-center gap-2 rounded-md p-2 text-left text-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <MessageSquare className="size-4 text-muted-foreground" aria-hidden="true" />
                      <span className="truncate">{c.title}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </TabsContent>
          <TabsContent value="files" className="min-h-0 flex-1 overflow-y-auto nexa-scrollbar">
            <p className="mb-2 text-xs text-muted-foreground">{t("project.filesNote")}</p>
            <input ref={fileInputRef} type="file" multiple className="hidden" onChange={(e) => { Array.from(e.target.files ?? []).forEach((file) => addFileToProject(project.id, file.name)); e.target.value = ""; }} />
            <Button size="sm" variant="outline" className="mb-2" onClick={() => fileInputRef.current?.click()}>
              <Plus className="size-4" aria-hidden="true" /> {t("project.addFileName")}
            </Button>
            {project.fileNames.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("project.noFiles")}</p>
            ) : (
              <ul className="space-y-1">
                {project.fileNames.map((fileName, idx) => (
                  <li key={`${fileName}-${idx}`} className="flex items-center gap-2 rounded-md p-2 text-sm">
                    <FileText className="size-4 text-muted-foreground" aria-hidden="true" /> {fileName}
                  </li>
                ))}
              </ul>
            )}
          </TabsContent>
          <TabsContent value="memory" className="min-h-0 flex-1 overflow-y-auto nexa-scrollbar">
            <ProjectMemoryTab projectId={project.id} />
          </TabsContent>
          <TabsContent value="instructions" className="min-h-0 flex-1">
            <Textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              onBlur={handleInstructionsBlur}
              placeholder={t("project.instructionsPlaceholder")}
              className="h-full min-h-32 resize-none"
              aria-label={t("project.instructions")}
            />
          </TabsContent>
          <TabsContent value="personalization" className="min-h-0 flex-1 space-y-3 overflow-y-auto nexa-scrollbar">
            <p className="text-xs text-muted-foreground">{t("personalization.desc")}</p>
            <label className="flex flex-col gap-1 text-sm">
              <span>{t("project.prefModel")}</span>
              <Input
                value={project.personalization?.preferredModel ?? ""}
                onChange={(e) =>
                  updateProject(project.id, {
                    personalization: { ...project.personalization, preferredModel: e.target.value || null },
                  })
                }
                className="h-9"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span>{t("project.prefStyle")}</span>
              <select
                className="h-9 rounded-lg border border-input bg-transparent px-2 text-sm"
                value={project.personalization?.responseStyle ?? ""}
                onChange={(e) =>
                  updateProject(project.id, {
                    personalization: {
                      ...project.personalization,
                      responseStyle: (e.target.value || null) as
                        | "concise"
                        | "balanced"
                        | "detailed"
                        | "technical"
                        | null,
                    },
                  })
                }
              >
                <option value="">—</option>
                <option value="concise">concise</option>
                <option value="balanced">balanced</option>
                <option value="detailed">detailed</option>
                <option value="technical">technical</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span>{t("project.prefLang")}</span>
              <Input
                value={project.personalization?.aiLanguage ?? ""}
                onChange={(e) =>
                  updateProject(project.id, {
                    personalization: { ...project.personalization, aiLanguage: e.target.value || null },
                  })
                }
                className="h-9"
              />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={project.personalization?.usePersonalContext !== false}
                onChange={(e) =>
                  updateProject(project.id, {
                    personalization: { ...project.personalization, usePersonalContext: e.target.checked },
                  })
                }
              />
              {t("project.usePersonal")}
            </label>
          </TabsContent>
        </Tabs>
        <Button variant="ghost" size="sm" className="self-start text-destructive hover:text-destructive" onClick={() => { deleteProject(project.id); closeProjects(); }}>
          <Trash2 className="size-4" aria-hidden="true" /> {t("project.deleteProject")}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
function ProjectMemoryTab({ projectId }: { projectId: string }) {
  const t = useT();
  const [items, setItems] = React.useState<MemoryItemApi[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [note, setNote] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const load = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await listMemory({ limit: 200 });
      setItems(response.results.map((r) => r.item).filter((item) => item.metadata?.project_id === projectId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the NEXA backend.");
    } finally {
      setLoading(false);
    }
  }, [projectId]);
  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);
  async function handleAdd() {
    if (!note.trim()) return;
    setSaving(true);
    try {
      const result = await createMemory({
        content: note.trim(),
        type: "long_term",
        metadata: { project_id: projectId },
        force: true,
      });
      if (!result.saved) {
        setError("Could not save this memory item.");
        return;
      }
      setNote("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save this memory item.");
    } finally {
      setSaving(false);
    }
  }
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">{t("project.memoryDesc")}</p>
      <div className="flex gap-2">
        <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("project.addNote")} onKeyDown={(e) => e.key === "Enter" && handleAdd()} aria-label={t("project.addNote")} />
        <Button size="sm" onClick={handleAdd} disabled={saving || !note.trim()}>
          {saving ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : t("memory.save")}
        </Button>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {loading ? (
        <p className="text-sm text-muted-foreground">{t("memory.loading")}</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("project.noMemory")}</p>
      ) : (
        <ul className="space-y-1">
          {items.map((item) => (
            <li key={item.id} className="rounded-md border border-border p-2 text-sm">{item.content}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
