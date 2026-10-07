"use client";
import { create } from "zustand";
import { toast } from "sonner";
import { createCrossover, realityEngine } from "@/lib/omniverse/explore-engine";
import { runLiveExplore } from "@/lib/omniverse/live-explore";
import type { OmniDiscovery, OmniMap, OmniNode, OmniNodeKind, OmniStatus } from "@/lib/omniverse/types";

/** Stable empty list so selectors never allocate a fresh `[]` each call. */
const EMPTY_DISCOVERIES: OmniDiscovery[] = [];

interface OmniverseState {
  map: OmniMap | null;
  selectedId: string | null;
  crossoverSelection: string[];
  query: string;
  kindFilter: OmniNodeKind | "ALL";
  statusFilter: OmniStatus | "ALL";
  camera: { x: number; y: number; zoom: number };
  goalDraft: string;
  exploreAbort: AbortController | null;
  livePhase: string | null;
  setGoalDraft: (v: string) => void;
  startMap: (goal?: string) => void;
  resetMap: () => void;
  selectNode: (id: string | null) => void;
  toggleExpand: (id: string) => void;
  toggleCrossoverPick: (id: string) => void;
  clearCrossover: () => void;
  runCrossover: () => boolean;
  runWhatIf: (assumptionId?: string) => boolean;
  runExperimentOnSelected: (outcome?: "success" | "mixed" | "fail") => boolean;
  detectShadow: () => void;
  setQuery: (q: string) => void;
  setKindFilter: (k: OmniNodeKind | "ALL") => void;
  setStatusFilter: (s: OmniStatus | "ALL") => void;
  setCamera: (c: Partial<OmniverseState["camera"]>) => void;
  startExplore: () => void;
  stopExplore: () => void;
  getSelected: () => OmniNode | null;
  getBestPaths: () => OmniNode[];
  getDiscoveries: () => OmniDiscovery[];
  getVisibleNodes: () => OmniNode[];
}

export const useOmniverseStore = create<OmniverseState>((set, get) => ({
  map: null,
  selectedId: null,
  crossoverSelection: [],
  query: "",
  kindFilter: "ALL",
  statusFilter: "ALL",
  camera: { x: 0, y: 0, zoom: 0.85 },
  goalDraft: "Create a successful AI product",
  exploreAbort: null,
  livePhase: null,
  setGoalDraft: (v) => set({ goalDraft: v }),
  startMap: (goal) => {
    get().stopExplore();
    const g = (goal ?? get().goalDraft).trim() || "Create a successful AI product";
    set({
      map: realityEngine.createSession(g, { demoMode: false }),
      selectedId: null,
      crossoverSelection: [],
      camera: { x: 0, y: 0, zoom: 0.85 },
      goalDraft: g,
      livePhase: null,
    });
  },
  resetMap: () => {
    get().stopExplore();
    set({ map: null, selectedId: null, crossoverSelection: [], livePhase: null });
  },
  selectNode: (id) => set({ selectedId: id }),
  toggleExpand: (id) => {
    const map = get().map;
    if (!map) return;
    set({
      map: {
        ...map,
        nodes: map.nodes.map((n) => (n.id === id ? { ...n, expanded: !n.expanded } : n)),
      },
    });
  },
  toggleCrossoverPick: (id) => {
    const cur = get().crossoverSelection;
    if (cur.includes(id)) {
      set({ crossoverSelection: cur.filter((x) => x !== id) });
      return;
    }
    if (cur.length >= 2) set({ crossoverSelection: [cur[1], id] });
    else set({ crossoverSelection: [...cur, id] });
  },
  clearCrossover: () => set({ crossoverSelection: [] }),
  runCrossover: () => {
    const { map, crossoverSelection } = get();
    if (!map || crossoverSelection.length !== 2) return false;
    const next = createCrossover(map, crossoverSelection[0], crossoverSelection[1]);
    if (!next) return false;
    const newNode = next.nodes[next.nodes.length - 1];
    set({ map: { ...next, demoMode: false }, crossoverSelection: [], selectedId: newNode.id });
    return true;
  },
  runWhatIf: (assumptionId) => {
    const map = get().map;
    if (!map) return false;
    const id =
      assumptionId ?? get().selectedId ?? map.nodes.find((n) => n.kind === "ASSUMPTION")?.id;
    if (!id) return false;
    const next = realityEngine.whatIf(map, id);
    if (!next) return false;
    const spawned = next.nodes.find((n) => n.whatIfOf === id);
    set({ map: { ...next, demoMode: false }, selectedId: spawned?.id ?? id });
    return true;
  },
  runExperimentOnSelected: (outcome = "success") => {
    const { map, selectedId } = get();
    if (!map || !selectedId) return false;
    const node = map.nodes.find((n) => n.id === selectedId);
    if (!node) return false;
    let next = map;
    let expId = node.experimentIds[0];
    if (node.kind === "HYPOTHESIS" || node.kind === "CROSSOVER" || node.kind === "ASSUMPTION") {
      next = realityEngine.createExperiment(next, node.id);
      expId = next.experiments[next.experiments.length - 1]?.id;
    } else if (node.kind === "EXPERIMENT") {
      expId = node.experimentIds[0];
    }
    if (!expId) return false;
    next = realityEngine.evaluateExperiment(next, expId, outcome);
    const result = [...next.nodes].reverse().find((n) => n.kind === "RESULT");
    set({ map: { ...next, demoMode: false }, selectedId: result?.id ?? selectedId });
    return true;
  },
  detectShadow: () => {
    const map = get().map;
    if (!map) return;
    const next = realityEngine.detectDiscoveries(map);
    const disc = next.nodes.find((n) => n.kind === "DISCOVERY" && !map.nodes.some((o) => o.id === n.id));
    set({ map: { ...next, demoMode: false }, selectedId: disc?.id ?? get().selectedId });
  },
  setQuery: (q) => set({ query: q }),
  setKindFilter: (k) => set({ kindFilter: k }),
  setStatusFilter: (s) => set({ statusFilter: s }),
  setCamera: (c) => set({ camera: { ...get().camera, ...c } }),
  startExplore: () => {
    const { map, stopExplore, goalDraft } = get();
    if (map?.exploring) return;
    stopExplore();
    const goal = (map?.goal || goalDraft).trim() || "Create a successful AI product";
    const controller = new AbortController();
    void (async () => {
      try {
        const { checkEntitlement, recordExperimentUsage } = await import("@/lib/billing-api");
        const gate = await checkEntitlement("omniverse");
        if (!gate.allowed) {
          toast("Upgrade required", {
            description: "OMNIVERSE is on Starter and above. Open Pricing to subscribe.",
            action: {
              label: "Pricing",
              onClick: () => {
                window.location.href = "/pricing";
              },
            },
          });
          return;
        }
        await recordExperimentUsage();
      } catch (err) {
        // If billing backend is unreachable, fail closed for paid features.
        toast("Billing check failed", {
          description: err instanceof Error ? err.message : "Could not verify plan entitlements.",
        });
        return;
      }
      const base = map ?? realityEngine.createSession(goal, { demoMode: false });
      set({
        exploreAbort: controller,
        livePhase: "GOAL",
        map: { ...base, goal, exploring: true, demoMode: false },
        selectedId: map ? get().selectedId : null,
        crossoverSelection: [],
        goalDraft: goal,
      });
      void runLiveExplore(
        goal,
        (phase, nextMap) => {
          if (controller.signal.aborted) return;
          set({ map: { ...nextMap, exploring: true, demoMode: false }, livePhase: phase });
        },
        controller.signal
      )
        .then((finalMap) => {
          if (controller.signal.aborted) return;
          set({
            map: { ...finalMap, exploring: false, demoMode: false },
            livePhase: "BEST PATHS",
            exploreAbort: null,
          });
          toast("Live exploration complete", {
            description: "Reality Engine updated the world model with live AI.",
          });
        })
        .catch((err) => {
          if (controller.signal.aborted || (err as Error)?.name === "AbortError") return;
          const current = get().map;
          set({
            map: current ? { ...current, exploring: false } : null,
            livePhase: null,
            exploreAbort: null,
          });
          toast("Live exploration failed", {
            description: err instanceof Error ? err.message : "Check backend / Ollama.",
          });
        });
    })();
  },
  stopExplore: () => {
    get().exploreAbort?.abort();
    const map = get().map;
    set({
      exploreAbort: null,
      livePhase: null,
      map: map ? { ...map, exploring: false } : null,
    });
  },
  getSelected: () => {
    const { map, selectedId } = get();
    if (!map || !selectedId) return null;
    return map.nodes.find((n) => n.id === selectedId) ?? null;
  },
  getBestPaths: () => {
    const map = get().map;
    if (!map) return [];
    return map.nodes
      .filter(
        (n) =>
          n.kind === "BEST_PATH" ||
          (n.status === "PROMISING" && (n.kind === "HYPOTHESIS" || n.kind === "CROSSOVER"))
      )
      .sort((a, b) => b.score.overall - a.score.overall);
  },
  getDiscoveries: () => {
    const discoveries = get().map?.discoveries;
    return discoveries ?? EMPTY_DISCOVERIES;
  },
  getVisibleNodes: () => {
    const { map, query, kindFilter, statusFilter } = get();
    if (!map) return [];
    const q = query.trim().toLowerCase();
    const collapsedParents = new Set(map.nodes.filter((n) => !n.expanded).map((n) => n.id));
    return map.nodes.filter((n) => {
      if (!n.visible) return false;
      if (kindFilter !== "ALL" && n.kind !== kindFilter) return false;
      if (statusFilter !== "ALL" && n.status !== statusFilter) return false;
      if (q && !`${n.title} ${n.summary}`.toLowerCase().includes(q)) return false;
      if (n.parentIds.some((p) => collapsedParents.has(p))) return false;
      return true;
    });
  },
}));
