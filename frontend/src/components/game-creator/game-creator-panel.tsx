"use client";
import * as React from "react";
import {
  Download,
  FileCode2,
  Maximize2,
  Play,
  RotateCcw,
  Square,
} from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  fetchBuildPreviewText,
  getBuildProject,
  resolveBuildExportUrl,
  resolveBuildPreviewUrl,
  runBuild,
} from "@/lib/api";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/store/chat-store";
import { useGameCreatorStore, type GameCreatorTab } from "@/store/game-creator-store";

const IFRAME_SANDBOX = "allow-scripts allow-pointer-lock allow-downloads";

export function GameCreatorPanel() {
  const t = useT();
  const open = useGameCreatorStore((s) => s.open);
  const closeGameCreator = useGameCreatorStore((s) => s.closeGameCreator);
  const projectId = useGameCreatorStore((s) => s.projectId);
  const previewUrl = useGameCreatorStore((s) => s.previewUrl);
  const title = useGameCreatorStore((s) => s.title);
  const files = useGameCreatorStore((s) => s.files);
  const tab = useGameCreatorStore((s) => s.tab);
  const setTab = useGameCreatorStore((s) => s.setTab);
  const selectedFile = useGameCreatorStore((s) => s.selectedFile);
  const setSelectedFile = useGameCreatorStore((s) => s.setSelectedFile);
  const fileContent = useGameCreatorStore((s) => s.fileContent);
  const setFileContent = useGameCreatorStore((s) => s.setFileContent);
  const sceneJson = useGameCreatorStore((s) => s.sceneJson);
  const setSceneJson = useGameCreatorStore((s) => s.setSceneJson);
  const setFiles = useGameCreatorStore((s) => s.setFiles);
  const consoleLines = useGameCreatorStore((s) => s.consoleLines);
  const pushConsole = useGameCreatorStore((s) => s.pushConsole);
  const clearConsole = useGameCreatorStore((s) => s.clearConsole);
  const previewRunning = useGameCreatorStore((s) => s.previewRunning);
  const previewKey = useGameCreatorStore((s) => s.previewKey);
  const runPreview = useGameCreatorStore((s) => s.runPreview);
  const stopPreview = useGameCreatorStore((s) => s.stopPreview);
  const restartPreview = useGameCreatorStore((s) => s.restartPreview);

  const activeConversationId = useChatStore((s) => s.activeConversationId);
  const [editHint, setEditHint] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const iframeRef = React.useRef<HTMLIFrameElement | null>(null);
  const wrapRef = React.useRef<HTMLDivElement | null>(null);

  const resolvedPreview = resolveBuildPreviewUrl(previewUrl);

  React.useEffect(() => {
    if (!open || !projectId) return;
    let cancelled = false;
    (async () => {
      try {
        const meta = await getBuildProject(projectId);
        if (cancelled) return;
        setFiles(meta.files ?? []);
        pushConsole("info", `Files: ${(meta.files ?? []).join(", ") || "—"}`);
      } catch (err) {
        if (!cancelled) pushConsole("warn", err instanceof Error ? err.message : "Failed to load project");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, projectId, setFiles, pushConsole]);

  React.useEffect(() => {
    if (!open || !projectId || !selectedFile) return;
    let cancelled = false;
    (async () => {
      try {
        const text = await fetchBuildPreviewText(projectId, selectedFile);
        if (!cancelled) setFileContent(text);
      } catch (err) {
        if (!cancelled) {
          setFileContent("");
          pushConsole("error", err instanceof Error ? err.message : "Read failed");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, projectId, selectedFile, setFileContent, pushConsole]);

  React.useEffect(() => {
    if (!open || !projectId || !files.includes("scene.json")) {
      setSceneJson(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const text = await fetchBuildPreviewText(projectId, "scene.json");
        if (!cancelled) setSceneJson(text);
      } catch {
        if (!cancelled) setSceneJson(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, projectId, files, setSceneJson]);

  React.useEffect(() => {
    if (!open) return;
    function onMessage(ev: MessageEvent) {
      const data = ev.data;
      if (!data || typeof data !== "object") return;
      if ((data as { type?: string }).type !== "nexa-game") return;
      const event = String((data as { event?: string }).event || "message");
      const genre = (data as { genre?: string }).genre;
      pushConsole("event", genre ? `${event} (${genre})` : event);
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [open, pushConsole]);

  async function applyEdit() {
    if (!projectId || !editHint.trim() || !activeConversationId) return;
    setBusy(true);
    pushConsole("info", `Edit: ${editHint.trim()}`);
    try {
      const build = await runBuild(editHint.trim(), {
        conversationId: activeConversationId,
        projectId,
      });
      if (build.files_created?.length || build.files_modified?.length) {
        const next = Array.from(
          new Set([...(files || []), ...(build.plan?.files ?? []), ...build.files_modified, ...build.files_created]),
        );
        setFiles(next);
      }
      pushConsole(build.success ? "info" : "error", build.message || (build.success ? "Updated" : "Edit failed"));
      restartPreview();
      if (selectedFile) {
        try {
          const text = await fetchBuildPreviewText(projectId, selectedFile);
          setFileContent(text);
        } catch {
          /* ignore */
        }
      }
    } catch (err) {
      pushConsole("error", err instanceof Error ? err.message : "Edit failed");
    } finally {
      setBusy(false);
    }
  }

  function enterFullscreen() {
    const el = wrapRef.current;
    if (!el) return;
    void el.requestFullscreen?.();
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && closeGameCreator()}>
      <DialogContent className="flex h-[min(42rem,90vh)] w-full max-w-5xl flex-col gap-2 overflow-hidden p-4">
        <DialogHeader className="pr-8">
          <DialogTitle className="truncate text-base font-semibold">
            {t("gameCreator.title")} · {title}
          </DialogTitle>
        </DialogHeader>

        <Tabs
          value={tab}
          onValueChange={(v) => setTab(v as GameCreatorTab)}
          className="flex min-h-0 flex-1 flex-col"
        >
          <TabsList className="flex h-auto flex-wrap justify-start gap-1">
            <TabsTrigger value="preview">{t("gameCreator.tab.preview")}</TabsTrigger>
            <TabsTrigger value="code">{t("gameCreator.tab.code")}</TabsTrigger>
            <TabsTrigger value="scene">{t("gameCreator.tab.scene")}</TabsTrigger>
            <TabsTrigger value="console">{t("gameCreator.tab.console")}</TabsTrigger>
            <TabsTrigger value="assets">{t("gameCreator.tab.assets")}</TabsTrigger>
            <TabsTrigger value="export">{t("gameCreator.tab.export")}</TabsTrigger>
          </TabsList>

          <TabsContent value="preview" className="mt-2 flex min-h-0 flex-1 flex-col gap-2">
            <div className="flex flex-wrap gap-2">
              <Button type="button" size="sm" variant="secondary" onClick={runPreview} disabled={previewRunning && !!resolvedPreview}>
                <Play className="size-3.5" /> {t("gameCreator.run")}
              </Button>
              <Button type="button" size="sm" variant="outline" onClick={stopPreview}>
                <Square className="size-3.5" /> {t("gameCreator.stop")}
              </Button>
              <Button type="button" size="sm" variant="outline" onClick={restartPreview}>
                <RotateCcw className="size-3.5" /> {t("gameCreator.restart")}
              </Button>
              <Button type="button" size="sm" variant="outline" onClick={enterFullscreen}>
                <Maximize2 className="size-3.5" /> {t("gameCreator.fullscreen")}
              </Button>
            </div>
            <div
              ref={wrapRef}
              className="relative min-h-0 flex-1 overflow-hidden rounded-xl border border-border/60 bg-black"
            >
              {previewRunning && resolvedPreview ? (
                <iframe
                  key={previewKey}
                  ref={iframeRef}
                  title={t("gameCreator.previewFrame")}
                  src={resolvedPreview}
                  sandbox={IFRAME_SANDBOX}
                  className="h-full w-full border-0"
                  allow="fullscreen"
                />
              ) : (
                <div className="grid h-full place-items-center text-sm text-muted-foreground">
                  {t("gameCreator.previewStopped")}
                </div>
              )}
            </div>
            <p className="text-xs text-muted-foreground">{t("gameCreator.sandboxHint")}</p>
          </TabsContent>

          <TabsContent value="code" className="mt-2 flex min-h-0 flex-1 flex-col gap-2">
            <div className="flex min-h-0 flex-1 gap-2">
              <ul className="w-36 shrink-0 overflow-y-auto rounded-lg border border-border/50 p-1 text-sm">
                {files.map((f) => (
                  <li key={f}>
                    <button
                      type="button"
                      className={cn(
                        "flex w-full items-center gap-1 rounded-md px-2 py-1.5 text-left hover:bg-muted/60",
                        selectedFile === f && "bg-muted",
                      )}
                      onClick={() => setSelectedFile(f)}
                    >
                      <FileCode2 className="size-3.5 opacity-60" />
                      <span className="truncate">{f}</span>
                    </button>
                  </li>
                ))}
              </ul>
              <Textarea
                readOnly
                value={fileContent}
                className="min-h-0 flex-1 resize-none font-mono text-xs"
                aria-label={selectedFile || "file"}
              />
            </div>
            <div className="flex gap-2">
              <input
                className="min-w-0 flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={editHint}
                onChange={(e) => setEditHint(e.target.value)}
                placeholder={t("gameCreator.editPlaceholder")}
                disabled={busy}
              />
              <Button type="button" size="sm" onClick={() => void applyEdit()} disabled={busy || !editHint.trim()}>
                {busy ? "…" : t("gameCreator.applyEdit")}
              </Button>
            </div>
          </TabsContent>

          <TabsContent value="scene" className="mt-2 min-h-0 flex-1 overflow-auto">
            {sceneJson ? (
              <pre className="rounded-lg border border-border/50 bg-muted/30 p-3 font-mono text-xs whitespace-pre-wrap">
                {sceneJson}
              </pre>
            ) : (
              <p className="text-sm text-muted-foreground">{t("gameCreator.noScene")}</p>
            )}
          </TabsContent>

          <TabsContent value="console" className="mt-2 flex min-h-0 flex-1 flex-col gap-2">
            <div className="flex justify-end">
              <Button type="button" size="sm" variant="ghost" onClick={clearConsole}>
                {t("gameCreator.clearConsole")}
              </Button>
            </div>
            <ul className="min-h-0 flex-1 overflow-y-auto rounded-lg border border-border/50 bg-black/40 p-2 font-mono text-xs">
              {consoleLines.length === 0 ? (
                <li className="text-muted-foreground">{t("gameCreator.consoleEmpty")}</li>
              ) : (
                consoleLines.map((line) => (
                  <li
                    key={line.id}
                    className={cn(
                      "py-0.5",
                      line.level === "error" && "text-red-400",
                      line.level === "warn" && "text-amber-300",
                      line.level === "event" && "text-cyan-300",
                      line.level === "info" && "text-zinc-300",
                    )}
                  >
                    <span className="opacity-50">{new Date(line.at).toLocaleTimeString()} </span>
                    {line.text}
                  </li>
                ))
              )}
            </ul>
          </TabsContent>

          <TabsContent value="assets" className="mt-2 min-h-0 flex-1 overflow-auto">
            <ul className="space-y-1 text-sm">
              {files.map((f) => (
                <li key={f} className="flex items-center justify-between rounded-md border border-border/40 px-3 py-2">
                  <span className="font-mono text-xs">{f}</span>
                  {projectId && (
                    <a
                      className="text-xs text-primary underline-offset-2 hover:underline"
                      href={resolveBuildPreviewUrl(`/api/v1/build/preview/${projectId}/${f}`) || "#"}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {t("gameCreator.openFile")}
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </TabsContent>

          <TabsContent value="export" className="mt-2 space-y-3">
            <p className="text-sm text-muted-foreground">{t("gameCreator.exportHint")}</p>
            {projectId ? (
              <a
                className={cn(buttonVariants(), "inline-flex gap-2")}
                href={resolveBuildExportUrl(projectId)}
                download
              >
                <Download className="size-4" /> {t("gameCreator.downloadZip")}
              </a>
            ) : null}
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
