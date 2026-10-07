"use client";
import {
  Compass,
  GitMerge,
  Loader2,
  Maximize2,
  Play,
  RotateCcw,
  Search,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useT } from "@/lib/i18n";
import type { OmniNodeKind, OmniStatus } from "@/lib/omniverse/types";
import { useOmniverseStore } from "@/store/omniverse-store";
import { OmniverseBestPaths } from "./best-paths-panel";
import { OmniverseDetailPanel } from "./detail-panel";
import { OmniverseGraph } from "./graph-canvas";

const KINDS: Array<OmniNodeKind | "ALL"> = [
  "ALL",
  "GOAL",
  "HYPOTHESIS",
  "RESEARCH",
  "ASSUMPTION",
  "DISCOVERY",
  "EXPERIMENT",
  "RESULT",
  "CROSSOVER",
  "BEST_PATH",
];
const STATUSES: Array<OmniStatus | "ALL"> = [
  "ALL",
  "NEW",
  "RESEARCHING",
  "TESTING",
  "VALIDATED",
  "PROMISING",
  "REJECTED",
];

export function OmniversePanel() {
  const t = useT();
  const map = useOmniverseStore((s) => s.map);
  const goalDraft = useOmniverseStore((s) => s.goalDraft);
  const setGoalDraft = useOmniverseStore((s) => s.setGoalDraft);
  const startMap = useOmniverseStore((s) => s.startMap);
  const startExplore = useOmniverseStore((s) => s.startExplore);
  const stopExplore = useOmniverseStore((s) => s.stopExplore);
  const resetMap = useOmniverseStore((s) => s.resetMap);
  const query = useOmniverseStore((s) => s.query);
  const setQuery = useOmniverseStore((s) => s.setQuery);
  const kindFilter = useOmniverseStore((s) => s.kindFilter);
  const setKindFilter = useOmniverseStore((s) => s.setKindFilter);
  const statusFilter = useOmniverseStore((s) => s.statusFilter);
  const setStatusFilter = useOmniverseStore((s) => s.setStatusFilter);
  const camera = useOmniverseStore((s) => s.camera);
  const setCamera = useOmniverseStore((s) => s.setCamera);
  const crossoverSelection = useOmniverseStore((s) => s.crossoverSelection);
  const runCrossover = useOmniverseStore((s) => s.runCrossover);
  const clearCrossover = useOmniverseStore((s) => s.clearCrossover);
  const livePhase = useOmniverseStore((s) => s.livePhase);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-border/60 bg-background/50 px-3 py-2.5 backdrop-blur-md">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <Compass className="size-4 shrink-0 text-primary" aria-hidden="true" />
          <div className="min-w-0">
            <p className="text-[10px] font-semibold tracking-[0.16em] text-muted-foreground uppercase">
              {t("omniverse.badge")}
              {map?.demoMode ? " · DEMO" : " · LIVE"}
              {livePhase ? ` · ${livePhase}` : ""}
            </p>
            <p className="truncate text-sm font-semibold">{t("omniverse.title")}</p>
          </div>
        </div>
        <Input
          value={goalDraft}
          onChange={(e) => setGoalDraft(e.target.value)}
          placeholder={t("omniverse.goalPlaceholder")}
          aria-label={t("omniverse.goalPlaceholder")}
          className="max-w-md"
          onKeyDown={(e) => {
            if (e.key === "Enter") startMap();
          }}
        />
        <Button type="button" variant="secondary" onClick={() => startMap()}>
          {t("omniverse.setGoal")}
        </Button>
        <Button
          type="button"
          onClick={() => {
            if (!map) startMap();
            window.setTimeout(() => startExplore(), map ? 0 : 30);
          }}
          disabled={Boolean(map?.exploring)}
          className="nexa-gradient-chat border-none text-white"
        >
          {map?.exploring ? (
            <>
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              {t("omniverse.exploring")}
            </>
          ) : (
            <>
              <Play className="size-4" aria-hidden="true" />
              EXPLORE
            </>
          )}
        </Button>
        {map?.exploring && (
          <Button type="button" variant="ghost" size="sm" onClick={stopExplore}>
            {t("omniverse.stop")}
          </Button>
        )}
        <Button
          type="button"
          variant="outline"
          disabled={crossoverSelection.length !== 2}
          onClick={() => runCrossover()}
        >
          <GitMerge className="size-4" aria-hidden="true" />
          CROSSOVER {crossoverSelection.length ? `(${crossoverSelection.length}/2)` : ""}
        </Button>
        {crossoverSelection.length > 0 && (
          <Button type="button" variant="ghost" size="sm" onClick={clearCrossover}>
            {t("omniverse.clearPick")}
          </Button>
        )}
        <Button type="button" variant="ghost" size="icon" aria-label={t("omniverse.reset")} onClick={resetMap}>
          <RotateCcw className="size-4" />
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-b border-border/40 px-3 py-2">
        <div className="relative min-w-[12rem] flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("omniverse.search")}
            className="pl-8"
          />
        </div>
        <select
          value={kindFilter}
          onChange={(e) => setKindFilter(e.target.value as OmniNodeKind | "ALL")}
          className="h-9 rounded-md border border-input bg-background px-2 text-xs"
          aria-label={t("omniverse.filterKind")}
        >
          {KINDS.map((k) => (
            <option key={k} value={k}>
              {k === "ALL" ? t("omniverse.allKinds") : k.replace("_", " ")}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as OmniStatus | "ALL")}
          className="h-9 rounded-md border border-input bg-background px-2 text-xs"
          aria-label={t("omniverse.filterStatus")}
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s === "ALL" ? t("omniverse.allStatuses") : s}
            </option>
          ))}
        </select>
        <div className="ml-auto flex items-center gap-1">
          <Button type="button" variant="ghost" size="icon" aria-label="Zoom out" onClick={() => setCamera({ zoom: Math.max(0.35, camera.zoom * 0.9) })}>
            <ZoomOut className="size-4" />
          </Button>
          <Button type="button" variant="ghost" size="icon" aria-label="Zoom in" onClick={() => setCamera({ zoom: Math.min(2.2, camera.zoom * 1.1) })}>
            <ZoomIn className="size-4" />
          </Button>
          <Button type="button" variant="ghost" size="icon" aria-label="Reset view" onClick={() => setCamera({ x: 0, y: 0, zoom: 0.85 })}>
            <Maximize2 className="size-4" />
          </Button>
        </div>
      </div>

      <div className="flex min-h-0 flex-1">
        <div className="relative min-w-0 flex-1">
          {map ? (
            <>
              {map.demoMode && (
                <p className="absolute top-3 right-3 z-10 max-w-xs rounded-md border border-amber-400/40 bg-amber-500/15 px-2.5 py-1.5 text-[11px] font-medium text-amber-100 backdrop-blur">
                  {t("omniverse.demoBanner")}
                </p>
              )}
              <OmniverseGraph />
              <OmniverseBestPaths />
              <p className="pointer-events-none absolute top-3 left-3 rounded-md bg-background/70 px-2 py-1 text-[11px] text-muted-foreground backdrop-blur">
                {t("omniverse.graphHint")}
              </p>
            </>
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
              <Compass className="size-10 text-primary opacity-80" />
              <h2 className="text-xl font-semibold">{t("omniverse.emptyTitle")}</h2>
              <p className="max-w-md text-sm text-muted-foreground">{t("omniverse.emptyDesc")}</p>
              <p className="max-w-md text-xs font-medium text-primary/90">{t("omniverse.tagline")}</p>
              <Button type="button" className="nexa-gradient-chat border-none text-white" onClick={() => { startMap(); window.setTimeout(() => startExplore(), 40); }}>
                <Play className="size-4" />
                EXPLORE
              </Button>
            </div>
          )}
        </div>
        <OmniverseDetailPanel />
      </div>
    </div>
  );
}
