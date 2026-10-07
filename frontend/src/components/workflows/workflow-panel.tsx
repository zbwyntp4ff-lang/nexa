"use client";
import * as React from "react";
import { GitBranch, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import {
  ApiError,
  createWorkflow,
  listWorkflows,
  workflowAction,
  type WorkflowApi,
} from "@/lib/api";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/store/ui-store";
const AUTONOMY = ["manual", "assisted", "autonomous"] as const;
function mark(status: string): string {
  if (status === "COMPLETED") return "✓";
  if (status === "RUNNING" || status === "WAITING_APPROVAL") return "⟳";
  if (status === "FAILED") return "✗";
  return "·";
}
export function WorkflowPanel() {
  const t = useT();
  const open = useUiStore((s) => s.workflowsOpen);
  const close = useUiStore((s) => s.closeWorkflows);
  const [items, setItems] = React.useState<WorkflowApi[]>([]);
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [goal, setGoal] = React.useState("");
  const [autonomy, setAutonomy] = React.useState<(typeof AUTONOMY)[number]>("assisted");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const selected = items.find((item) => item.id === selectedId) ?? null;
  const refresh = React.useCallback(async () => {
    setLoading(true);
    try {
      const next = await listWorkflows();
      setItems(next);
      setError(null);
      setSelectedId((current) => current ?? next[0]?.id ?? null);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not load workflows.");
    } finally {
      setLoading(false);
    }
  }, []);
  React.useEffect(() => {
    if (!open) return;
    // Fetch when the panel opens. The request is the external system.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [open, refresh]);
  React.useEffect(() => {
    if (!open || !selected || !["RUNNING", "PENDING"].includes(selected.status)) return;
    const timer = window.setInterval(() => void refresh(), 3000);
    return () => window.clearInterval(timer);
  }, [open, selected, refresh]);
  async function onCreate() {
    const text = goal.trim();
    if (!text) return;
    setBusy(true);
    setError(null);
    try {
      const created = await createWorkflow(text, autonomy);
      setGoal("");
      setItems((current) => [created, ...current]);
      setSelectedId(created.id);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : t("workflows.failed"));
    } finally {
      setBusy(false);
    }
  }
  async function act(action: "start" | "pause" | "resume" | "cancel" | "approve" | "reject") {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await workflowAction(selected.id, action);
      setItems((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : t("workflows.failed"));
    } finally {
      setBusy(false);
    }
  }
  const percent = Math.round((selected?.progress ?? 0) * 100);
  return (
    <Dialog open={open} onOpenChange={(next) => !next && close()}>
      <DialogContent className="flex max-h-[85dvh] flex-col gap-4 overflow-hidden sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <GitBranch className="size-4 text-primary" aria-hidden="true" />
            {t("workflows.title")}
          </DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">{t("workflows.desc")}</p>
        <div className="grid gap-2">
          <label className="text-xs font-medium text-muted-foreground" htmlFor="workflow-goal">
            {t("workflows.goal")}
          </label>
          <Textarea
            id="workflow-goal"
            value={goal}
            onChange={(event) => setGoal(event.target.value)}
            placeholder={t("workflows.goalPlaceholder")}
            rows={2}
          />
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-xs text-muted-foreground" htmlFor="workflow-autonomy">
              {t("workflows.autonomy")}
            </label>
            <select
              id="workflow-autonomy"
              value={autonomy}
              onChange={(event) => setAutonomy(event.target.value as (typeof AUTONOMY)[number])}
              className="rounded-md border border-border bg-background px-2 py-1 text-sm"
            >
              {AUTONOMY.map((level) => (
                <option key={level} value={level}>
                  {t(`workflows.${level}`)}
                </option>
              ))}
            </select>
            <Button type="button" onClick={() => void onCreate()} disabled={busy || !goal.trim()}>
              {t("workflows.create")}
            </Button>
          </div>
        </div>
        {loading && items.length === 0 && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            {t("workflows.loading")}
          </p>
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}
        <div className="grid min-h-0 flex-1 gap-3 overflow-hidden md:grid-cols-[220px_1fr]">
          <ul className="nexa-scrollbar max-h-48 space-y-1 overflow-y-auto md:max-h-none" aria-label={t("workflows.title")}>
            {items.length === 0 && !loading ? (
              <li className="text-sm text-muted-foreground">{t("workflows.empty")}</li>
            ) : (
              items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(item.id)}
                    className={cn(
                      "w-full rounded-md px-2 py-1.5 text-left text-sm",
                      item.id === selectedId ? "bg-accent text-accent-foreground" : "hover:bg-accent/60"
                    )}
                  >
                    <span className="block truncate font-medium">{item.name}</span>
                    <span className="text-xs text-muted-foreground">{item.status}</span>
                  </button>
                </li>
              ))
            )}
          </ul>
          {selected && (
            <div className="nexa-scrollbar min-h-0 space-y-3 overflow-y-auto pr-1">
              <div>
                <h3 className="font-medium">{selected.name}</h3>
                <p className="text-sm text-muted-foreground">{selected.description}</p>
              </div>
              <p className="text-xs text-muted-foreground">
                {t("workflows.autonomy")}: {t(`workflows.${selected.autonomy}`)}
              </p>
              <div>
                <div className="mb-1 flex justify-between text-xs text-muted-foreground">
                  <span>{t("workflows.progress")}</span>
                  <span>{percent}%</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
                  <div className="h-full bg-primary" style={{ width: `${percent}%` }} />
                </div>
              </div>
              <ul className="space-y-1 text-sm">
                {selected.tasks.map((task) => (
                  <li key={task.id}>
                    <span aria-hidden="true">{mark(task.status)} </span>
                    {task.name}
                    {task.error ? <span className="text-destructive"> — {task.error}</span> : null}
                  </li>
                ))}
              </ul>
              <p className="text-sm">
                {t("workflows.current")}: {selected.current_task ?? "—"}
              </p>
              <p className="text-sm font-medium">Status: {selected.status}</p>
              {selected.error && (
                <p className="text-sm text-destructive">
                  {t("workflows.error")}: {selected.error}
                </p>
              )}
              <div>
                <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{t("workflows.checkpoints")}</p>
                {selected.checkpoints.length === 0 ? (
                  <p className="text-sm text-muted-foreground">{t("workflows.noCheckpoints")}</p>
                ) : (
                  <ul className="text-sm">
                    {selected.checkpoints.map((item) => (
                      <li key={item.name}>✓ {item.name}</li>
                    ))}
                  </ul>
                )}
              </div>
              {selected.pending_approval && (
                <div className="rounded-md border border-border bg-card p-3 text-sm">
                  <p className="font-medium">{t("workflows.approvalTitle")}</p>
                  <p>Agent: {selected.pending_approval.agent}</p>
                  <p>{selected.pending_approval.action}</p>
                  <p>
                    {t("workflows.files")}: {selected.pending_approval.resources.length}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button type="button" onClick={() => void act("approve")} disabled={busy}>
                      {t("workflows.approve")}
                    </Button>
                    <Button type="button" variant="secondary" onClick={() => void act("reject")} disabled={busy}>
                      {t("workflows.reject")}
                    </Button>
                    <Button type="button" variant="ghost" onClick={() => void act("cancel")} disabled={busy}>
                      {t("workflows.cancel")}
                    </Button>
                  </div>
                </div>
              )}
              {selected.final_result && selected.status === "COMPLETED" && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground">{t("workflows.result")}</p>
                  <p className="whitespace-pre-wrap text-sm">{selected.final_result}</p>
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                {selected.status === "PENDING" && (
                  <Button type="button" onClick={() => void act("start")} disabled={busy}>
                    {t("workflows.start")}
                  </Button>
                )}
                {selected.status === "PAUSED" || selected.status === "FAILED" ? (
                  <Button type="button" onClick={() => void act("resume")} disabled={busy}>
                    {t("workflows.resume")}
                  </Button>
                ) : null}
                {selected.status === "RUNNING" && (
                  <Button type="button" variant="secondary" onClick={() => void act("pause")} disabled={busy}>
                    {t("workflows.pause")}
                  </Button>
                )}
                {selected.status !== "COMPLETED" && selected.status !== "CANCELLED" && !selected.pending_approval && (
                  <Button type="button" variant="ghost" onClick={() => void act("cancel")} disabled={busy}>
                    {t("workflows.cancel")}
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
