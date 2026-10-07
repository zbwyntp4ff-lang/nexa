"use client";
import { Beaker, FlaskConical, HelpCircle, Radar } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";
import type { OmniDiscovery, OmniNode } from "@/lib/omniverse/types";
import { useOmniverseStore } from "@/store/omniverse-store";

const EMPTY_DISCOVERIES: OmniDiscovery[] = [];

export function OmniverseDetailPanel() {
  const t = useT();
  const map = useOmniverseStore((s) => s.map);
  const selectedId = useOmniverseStore((s) => s.selectedId);
  const selected: OmniNode | null =
    map && selectedId ? (map.nodes.find((n) => n.id === selectedId) ?? null) : null;
  const runWhatIf = useOmniverseStore((s) => s.runWhatIf);
  const runExperimentOnSelected = useOmniverseStore((s) => s.runExperimentOnSelected);
  const detectShadow = useOmniverseStore((s) => s.detectShadow);
  // Prefer map.discoveries directly — `getDiscoveries()` used `?? []`, which
  // allocated a new array every selector call and triggered React #185.
  const discoveries = map?.discoveries ?? EMPTY_DISCOVERIES;

  if (!selected || !map) {
    return (
      <aside className="nexa-glass hidden h-full w-80 shrink-0 flex-col overflow-y-auto rounded-none border-l border-border p-4 lg:flex">
        <h2 className="text-sm font-semibold">{t("omniverse.details")}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{t("omniverse.selectHint")}</p>
        {map && (
          <Button type="button" variant="outline" className="mt-4" onClick={detectShadow}>
            <Radar className="size-4" aria-hidden="true" />
            {t("omniverse.shadowScan")}
          </Button>
        )}
      </aside>
    );
  }

  const experiments = map.experiments.filter(
    (e) => selected.experimentIds.includes(e.id) || e.hypothesisId === selected.id
  );
  const parents = map.nodes.filter((n) => selected.parentIds.includes(n.id));
  const relatedDiscoveries = discoveries.filter(
    (d) => d.nodeId === selected.id || d.relatedNodeIds.includes(selected.id)
  );
  const score = selected.score;
  const canWhatIf = selected.kind === "ASSUMPTION";
  const canExperiment =
    selected.kind === "HYPOTHESIS" ||
    selected.kind === "CROSSOVER" ||
    selected.kind === "ASSUMPTION" ||
    selected.kind === "EXPERIMENT";

  return (
    <aside className="nexa-glass flex h-full w-full shrink-0 flex-col overflow-y-auto border-l border-border p-4 lg:w-80">
      <p className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
        {selected.kind.replaceAll("_", " ")}
        {selected.discoveryKind ? ` · ${selected.discoveryKind.replaceAll("_", " ")}` : ""}
      </p>
      <h2 className="mt-1 text-base font-semibold leading-snug">{selected.title}</h2>
      <p className="mt-1 text-xs text-muted-foreground">{selected.summary}</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        <span className="rounded-md bg-muted px-2 py-0.5 text-[11px] font-medium">{selected.status}</span>
        <span className="rounded-md bg-primary/15 px-2 py-0.5 text-[11px] font-medium text-primary">
          score {score.overall}
        </span>
        {map.demoMode && (
          <span className="rounded-md border border-amber-400/50 bg-amber-500/15 px-2 py-0.5 text-[11px] font-semibold text-amber-200">
            DEMO
          </span>
        )}
      </div>

      <div className="mt-4 flex flex-col gap-2">
        {canWhatIf && (
          <Button type="button" variant="secondary" onClick={() => runWhatIf(selected.id)}>
            <HelpCircle className="size-4" aria-hidden="true" />
            {t("omniverse.whatIf")}
          </Button>
        )}
        {canExperiment && (
          <>
            <Button type="button" onClick={() => runExperimentOnSelected("success")}>
              <FlaskConical className="size-4" aria-hidden="true" />
              {t("omniverse.runExperiment")}
            </Button>
            <div className="flex gap-1">
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="flex-1"
                onClick={() => runExperimentOnSelected("mixed")}
              >
                {t("omniverse.outcomeMixed")}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="flex-1"
                onClick={() => runExperimentOnSelected("fail")}
              >
                {t("omniverse.outcomeFail")}
              </Button>
            </div>
          </>
        )}
        <Button type="button" variant="outline" onClick={detectShadow}>
          <Radar className="size-4" aria-hidden="true" />
          {t("omniverse.shadowScan")}
        </Button>
      </div>

      <section className="mt-5 space-y-2">
        <h3 className="text-xs font-semibold tracking-wide uppercase">{t("omniverse.whyPath")}</h3>
        <p className="text-sm leading-relaxed">{selected.why}</p>
        {selected.rejectedReason && (
          <p className="rounded-lg border border-rose-400/40 bg-rose-500/10 px-2.5 py-2 text-xs text-rose-200">
            {t("omniverse.rejectedBecause")}: {selected.rejectedReason}
          </p>
        )}
      </section>

      <section className="mt-5 space-y-2">
        <h3 className="text-xs font-semibold tracking-wide uppercase">{t("omniverse.scoring")}</h3>
        {(
          [
            ["potential", score.potential],
            ["evidence", score.evidence],
            ["confidence", score.confidence],
            ["feasibility", score.feasibility],
            ["novelty", score.novelty],
            ["overall", score.overall],
          ] as const
        ).map(([k, v]) => (
          <div key={k} className="space-y-1">
            <div className="flex justify-between text-[11px]">
              <span className="capitalize text-muted-foreground">{k}</span>
              <span className="tabular-nums">{v}</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full nexa-gradient-chat" style={{ width: `${v}%` }} />
            </div>
          </div>
        ))}
      </section>

      <section className="mt-5 space-y-2">
        <h3 className="text-xs font-semibold tracking-wide uppercase">{t("omniverse.worldModel")}</h3>
        <p className="text-[11px] text-muted-foreground">
          {t("omniverse.knowns")}: {map.worldModel.knowns.slice(-3).join(" · ") || "—"}
        </p>
        <p className="text-[11px] text-muted-foreground">
          {t("omniverse.unknowns")}: {map.worldModel.unknowns.slice(-3).join(" · ") || "—"}
        </p>
      </section>

      <section className="mt-5 space-y-2">
        <h3 className="text-xs font-semibold tracking-wide uppercase">{t("omniverse.evidence")}</h3>
        <ul className="space-y-1">
          {selected.evidence.map((e) => (
            <li key={e} className="rounded-md bg-muted/50 px-2 py-1.5 text-xs">
              {e}
            </li>
          ))}
        </ul>
      </section>

      {relatedDiscoveries.length > 0 && (
        <section className="mt-5 space-y-2">
          <h3 className="text-xs font-semibold tracking-wide uppercase">{t("omniverse.shadow")}</h3>
          {relatedDiscoveries.map((d) => (
            <div key={d.id} className="rounded-lg border border-amber-400/30 bg-amber-500/10 p-2.5 text-xs space-y-1">
              <p className="font-medium">{d.title}</p>
              <p className="text-muted-foreground">
                conf {d.confidence} · pot {d.potential}
              </p>
              <p>
                {t("omniverse.nextAction")}: {d.nextAction}
              </p>
            </div>
          ))}
        </section>
      )}

      {parents.length > 0 && (
        <section className="mt-5 space-y-2">
          <h3 className="text-xs font-semibold tracking-wide uppercase">{t("omniverse.parents")}</h3>
          <ul className="space-y-1">
            {parents.map((p) => (
              <li key={p.id} className="text-xs text-muted-foreground">
                {p.kind}: {p.title}
              </li>
            ))}
          </ul>
        </section>
      )}

      {experiments.length > 0 && (
        <section className="mt-5 space-y-2">
          <h3 className="flex items-center gap-1 text-xs font-semibold tracking-wide uppercase">
            <Beaker className="size-3.5" aria-hidden="true" />
            {t("omniverse.experiments")}
          </h3>
          {experiments.map((ex) => (
            <div key={ex.id} className="space-y-1 rounded-lg border border-border bg-background/40 p-2.5 text-xs">
              <p className="font-medium">{ex.objective}</p>
              <p className="text-muted-foreground">
                {t("omniverse.method")}: {ex.method}
              </p>
              <p>
                {t("omniverse.expected")}: {ex.expectedResult}
              </p>
              <p>
                {t("omniverse.actual")}: {ex.actualResult || "—"}
              </p>
              <p className="font-medium">{ex.status}</p>
            </div>
          ))}
        </section>
      )}
    </aside>
  );
}
