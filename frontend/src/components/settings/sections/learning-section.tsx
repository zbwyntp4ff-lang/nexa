"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  generateLearningProposals,
  getLearningStatus,
  listLearningProposals,
  runLearningEval,
  setLearningProposalStatus,
  updateLearningSettings,
  type ImprovementProposalApi,
  type LearningStatusApi,
} from "@/lib/learning-api";
import { useT } from "@/lib/i18n";

function ToggleRow({
  label,
  description,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-4 rounded-md border border-border/60 px-3 py-2.5">
      <span className="min-w-0">
        <span className="block text-sm font-medium">{label}</span>
        <span className="mt-0.5 block text-xs text-muted-foreground">{description}</span>
      </span>
      <input
        type="checkbox"
        className="mt-1 size-4 accent-foreground"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
    </label>
  );
}

export function LearningSection() {
  const t = useT();
  const [status, setStatus] = React.useState<LearningStatusApi | null>(null);
  const [proposals, setProposals] = React.useState<ImprovementProposalApi[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const refresh = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, p] = await Promise.all([getLearningStatus(), listLearningProposals()]);
      setStatus(s);
      setProposals(p);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("learning.loadError"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  async function patch(
    next: Partial<{
      memory_enabled: boolean;
      feedback_enabled: boolean;
      auto_knowledge_base: boolean;
      allow_cloud_on_documents: boolean;
    }>,
  ) {
    if (!status) return;
    setBusy(true);
    setError(null);
    try {
      const settings = await updateLearningSettings(next);
      setStatus({ ...status, settings, memory_enabled: settings.memory_enabled });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("learning.saveError"));
    } finally {
      setBusy(false);
    }
  }

  async function handleEval() {
    setBusy(true);
    setError(null);
    try {
      const stats = await runLearningEval();
      await refresh();
      if (status) {
        setStatus({
          ...status,
          feedback_stats: stats,
          last_eval_summary: stats.summary,
        });
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("learning.evalError"));
    } finally {
      setBusy(false);
    }
  }

  async function handleGenerate() {
    setBusy(true);
    setError(null);
    try {
      const created = await generateLearningProposals();
      setProposals((prev) => [...created, ...prev]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("learning.proposeError"));
    } finally {
      setBusy(false);
    }
  }

  if (loading && !status) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        {t("learning.loading")}
      </div>
    );
  }

  const s = status?.settings;

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-medium">{t("learning.title")}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{t("learning.desc")}</p>
      </div>

      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}

      <div className="grid gap-2 sm:grid-cols-2">
        <div className="rounded-md border border-border/60 px-3 py-2">
          <p className="text-xs text-muted-foreground">{t("learning.statMemory")}</p>
          <p className="text-lg font-semibold">{status?.memory_item_count ?? 0}</p>
        </div>
        <div className="rounded-md border border-border/60 px-3 py-2">
          <p className="text-xs text-muted-foreground">{t("learning.statDocs")}</p>
          <p className="text-lg font-semibold">{status?.knowledge_document_count ?? 0}</p>
        </div>
        <div className="rounded-md border border-border/60 px-3 py-2">
          <p className="text-xs text-muted-foreground">{t("learning.statFeedback")}</p>
          <p className="text-lg font-semibold">{status?.feedback_stats.total ?? 0}</p>
        </div>
        <div className="rounded-md border border-border/60 px-3 py-2">
          <p className="text-xs text-muted-foreground">{t("learning.statIndex")}</p>
          <p className="text-sm font-medium">
            {status?.last_index_at
              ? new Date(status.last_index_at).toLocaleString()
              : t("learning.never")}
          </p>
        </div>
      </div>

      <div className="space-y-2">
        <ToggleRow
          label={t("learning.memoryEnabled")}
          description={t("learning.memoryEnabledDesc")}
          checked={!!s?.memory_enabled}
          disabled={busy}
          onChange={(v) => void patch({ memory_enabled: v })}
        />
        <ToggleRow
          label={t("learning.feedbackEnabled")}
          description={t("learning.feedbackEnabledDesc")}
          checked={!!s?.feedback_enabled}
          disabled={busy}
          onChange={(v) => void patch({ feedback_enabled: v })}
        />
        <ToggleRow
          label={t("learning.autoKb")}
          description={t("learning.autoKbDesc")}
          checked={!!s?.auto_knowledge_base}
          disabled={busy}
          onChange={(v) => void patch({ auto_knowledge_base: v })}
        />
        <ToggleRow
          label={t("learning.cloudDocs")}
          description={t("learning.cloudDocsDesc")}
          checked={!!s?.allow_cloud_on_documents}
          disabled={busy}
          onChange={(v) => void patch({ allow_cloud_on_documents: v })}
        />
      </div>

      <div className="space-y-2 rounded-md border border-border/60 p-3">
        <h4 className="text-sm font-medium">{t("learning.evalTitle")}</h4>
        <p className="text-xs text-muted-foreground">
          {status?.last_eval_summary || status?.feedback_stats.summary || t("learning.evalEmpty")}
        </p>
        {status?.feedback_stats.positive_ratio != null && (
          <p className="text-sm">
            {t("learning.positiveRatio")}:{" "}
            {Math.round(status.feedback_stats.positive_ratio * 100)}%
          </p>
        )}
        <div className="flex flex-wrap gap-2 pt-1">
          <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => void handleEval()}>
            {t("learning.runEval")}
          </Button>
          <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => void handleGenerate()}>
            {t("learning.generateProposals")}
          </Button>
        </div>
      </div>

      <div className="space-y-2">
        <h4 className="text-sm font-medium">{t("learning.mechanisms")}</h4>
        <ul className="list-inside list-disc text-sm text-muted-foreground">
          {(status?.mechanisms ?? []).map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
        <p className="text-xs text-muted-foreground">{status?.fine_tuning.note}</p>
        <p className="text-xs text-muted-foreground">
          {t("learning.needsConfirm")}: {(status?.requires_confirmation ?? []).join(", ")}
        </p>
      </div>

      {proposals.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium">{t("learning.proposals")}</h4>
          <ul className="space-y-2">
            {proposals.map((p) => (
              <li key={p.id} className="rounded-md border border-border/60 p-3 text-sm">
                <p className="font-medium">
                  {p.title}{" "}
                  <span className="text-xs font-normal text-muted-foreground">({p.status})</span>
                </p>
                <p className="mt-1 text-xs text-muted-foreground">{p.rationale}</p>
                <p className="mt-1 text-xs">{p.suggested_change}</p>
                {p.before_summary && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {t("learning.before")}: {p.before_summary}
                  </p>
                )}
                {p.after_summary && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {t("learning.after")}: {p.after_summary}
                    {p.improved != null && (
                      <> — {p.improved ? t("learning.improved") : t("learning.notImproved")}</>
                    )}
                  </p>
                )}
                <div className="mt-2 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={busy || p.status === "accepted"}
                    onClick={() =>
                      void setLearningProposalStatus(p.id, "accepted").then((u) =>
                        setProposals((prev) => prev.map((x) => (x.id === u.id ? u : x))),
                      )
                    }
                  >
                    {t("learning.accept")}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={busy || p.status === "rejected"}
                    onClick={() =>
                      void setLearningProposalStatus(p.id, "rejected").then((u) =>
                        setProposals((prev) => prev.map((x) => (x.id === u.id ? u : x))),
                      )
                    }
                  >
                    {t("learning.reject")}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    disabled={busy || p.status === "applied" || p.status === "rejected"}
                    onClick={() =>
                      void setLearningProposalStatus(p.id, "applied").then((u) =>
                        setProposals((prev) => prev.map((x) => (x.id === u.id ? u : x))),
                      )
                    }
                  >
                    {t("learning.applyMeasured")}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
