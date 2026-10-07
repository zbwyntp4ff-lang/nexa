/**
 * NEXA Reality Engine — ExplorationEngine.
 *
 * Builds a living problem model: hypotheses → research → shadow discoveries →
 * experiments → model updates → ranked best paths.
 *
 * When a live backend/AI provider is not wired for this flow, callers use
 * DEMO MODE (OmniMap.demoMode === true). Demo logic stays in this module and
 * is labeled in the UI — never silently presented as production AI output.
 */
import { computeScore, scoreFromExperimentOutcome, statusFromScore } from "./scoring";
import type {
  OmniDiscovery,
  OmniEdge,
  OmniExperiment,
  OmniMap,
  OmniNode,
  OmniNodeKind,
  OmniScore,
  OmniStatus,
  ShadowKind,
  WorldModel,
} from "./types";

function uid(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 9)}`;
}

function now(): number {
  return Date.now();
}

function placeAround(cx: number, cy: number, index: number, total: number, radius: number) {
  const angle = -Math.PI / 2 + (index / Math.max(total, 1)) * Math.PI * 2;
  return { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius };
}

function emptyWorld(goal: string): WorldModel {
  return {
    goal,
    knowns: ["User stated a goal"],
    unknowns: ["Demand signal", "Must-have vs nice-to-have", "Go-to-market wedge"],
    assumptions: [],
    contradictions: [],
    openQuestions: ["What would falsify the leading hypothesis?"],
    lastUpdatedAt: new Date().toISOString(),
  };
}

function addNode(
  map: OmniMap,
  partial: Omit<OmniNode, "bornAt" | "visible" | "expanded" | "score"> & { score?: OmniScore },
  fromId?: string,
  edgeKind: OmniEdge["kind"] = "flow"
): OmniMap {
  const node: OmniNode = {
    ...partial,
    score: partial.score ?? computeScore({}),
    expanded: true,
    bornAt: now(),
    visible: true,
  };
  const edges = [...map.edges];
  if (fromId) {
    edges.push({
      id: uid("edge"),
      from: fromId,
      to: node.id,
      kind: edgeKind,
      label: edgeKind === "crossover" ? "crossover" : edgeKind === "whatif" ? "what if" : undefined,
    });
  }
  return { ...map, nodes: [...map.nodes, node], edges };
}

function updateNode(map: OmniMap, id: string, patch: Partial<OmniNode>): OmniMap {
  return { ...map, nodes: map.nodes.map((n) => (n.id === id ? { ...n, ...patch } : n)) };
}

function topicFromGoal(goal: string): string {
  const words = goal.replace(/[^a-zA-Zа-яА-Я0-9\s]/g, "").trim().split(/\s+/).slice(0, 4);
  return words.join(" ") || "AI product";
}

const SHADOW_META: Record<
  ShadowKind,
  { title: (t: string) => string; next: string; confidence: number; potential: number }
> = {
  HIDDEN_ASSUMPTION: {
    title: (t) => `Hidden assumption: users already feel pain around “${t}”`,
    next: "Pressure-test with 5 problem interviews before building.",
    confidence: 62,
    potential: 78,
  },
  ALTERNATIVE_PATH: {
    title: () => "Alternative path: serve operators, not end consumers first",
    next: "Sketch a B2B wedge and compare willingness-to-pay.",
    confidence: 55,
    potential: 72,
  },
  UNEXPECTED_CONNECTION: {
    title: () => "Unexpected connection: support workflows ↔ retention loop",
    next: "Map one support ticket type that could become productized insight.",
    confidence: 48,
    potential: 80,
  },
  MISSING_EVIDENCE: {
    title: () => "Missing evidence: no activation metric defined",
    next: "Define a single activation event and measure a 20-user cohort.",
    confidence: 70,
    potential: 65,
  },
  HIGH_INFO_EXPERIMENT: {
    title: () => "High-information experiment: concierge MVP before automation",
    next: "Run a manual concierge for 7 days; record time-to-value.",
    confidence: 66,
    potential: 84,
  },
  CONTRADICTION: {
    title: () => "Contradiction: “platform” ambition vs beachhead urgency",
    next: "Time-box platform work; force a one-workflow ship date.",
    confidence: 58,
    potential: 70,
  },
  BLIND_SPOT: {
    title: () => "Blind spot: distribution channel assumed to be organic",
    next: "List 3 paid/partner channels and estimate CAC ceilings.",
    confidence: 60,
    potential: 75,
  },
  FORGE_COMBINATION: {
    title: () => "FORGE: combine beachhead workflow + insight loop into one wedge",
    next: "Draft one experiment that tests the joined mechanism, not two separate bets.",
    confidence: 52,
    potential: 82,
  },
  BREAKTHROUGH_LINK: {
    title: () => "BREAKTHROUGH: distant link between support friction and pricing power",
    next: "Treat as HYPOTHESIS — design a validation probe before claiming fact.",
    confidence: 44,
    potential: 88,
  },
};

export class ExplorationEngine {
  createSession(goal: string, opts?: { demoMode?: boolean }): OmniMap {
    const title = goal.trim() || "Untitled goal";
    const goalId = uid("goal");
    const demoMode = opts?.demoMode ?? false;
    const goalNode: OmniNode = {
      id: goalId,
      kind: "GOAL",
      title,
      summary: demoMode
        ? "DEMO MODE session — synthetic exploration of the living problem model."
        : "Root objective for live exploration.",
      status: "NEW",
      score: computeScore({ potential: 90, evidence: 20, confidence: 40, feasibility: 55, novelty: 70 }),
      parentIds: [],
      why: "User-defined goal that seeds Reality Engine exploration.",
      evidence: ["User intent"],
      experimentIds: [],
      x: 0,
      y: 0,
      expanded: true,
      bornAt: now(),
      visible: true,
    };
    return {
      id: uid("map"),
      goal: title,
      createdAt: new Date().toISOString(),
      exploring: false,
      demoMode,
      worldModel: emptyWorld(title),
      nodes: [goalNode],
      edges: [],
      experiments: [],
      discoveries: [],
    };
  }

  generateHypotheses(map: OmniMap, parentId?: string, count = 3): OmniMap {
    const goalNode = map.nodes.find((n) => n.kind === "GOAL")!;
    const parent = parentId ? map.nodes.find((n) => n.id === parentId) : goalNode;
    if (!parent) return map;
    const topic = topicFromGoal(map.goal);
    const seeds = [
      { title: "Product wedge", summary: `Narrow beachhead around ${topic} with clear willingness to pay.` },
      { title: "Workflow agent", summary: `Agent that finishes a recurring high-value job for ${topic}.` },
      { title: "Data flywheel", summary: `Unique data loop that improves ${topic} with usage.` },
      { title: "Platform layer", summary: `Reusable substrate others build on for ${topic}.` },
    ];
    let next = map;
    seeds.slice(0, count).forEach((d, i) => {
      const id = uid("hyp");
      const pos = placeAround(parent.x, parent.y, i, count, parent.kind === "GOAL" ? 220 : 160);
      next = addNode(
        next,
        {
          id,
          kind: "HYPOTHESIS",
          title: d.title,
          summary: d.summary,
          status: "NEW",
          parentIds: [parent.id],
          why: `Hypothesis derived from “${parent.title}” to make the goal testable.`,
          evidence: parent.kind === "GOAL" ? ["Goal decomposition"] : [`Parent: ${parent.title}`],
          experimentIds: [],
          x: pos.x,
          y: pos.y + (parent.kind === "GOAL" ? 0 : 80),
          score: computeScore({
            potential: 60 + i * 8,
            evidence: 25,
            confidence: 35,
            feasibility: 55 - i * 5,
            novelty: 50 + i * 7,
          }),
        },
        parent.id
      );
    });
    return next;
  }

  researchHypothesis(map: OmniMap, hypothesisId: string): OmniMap {
    const hyp = map.nodes.find((n) => n.id === hypothesisId);
    if (!hyp) return map;
    const id = uid("res");
    let next = addNode(
      map,
      {
        id,
        kind: "RESEARCH",
        title: `Research: ${hyp.title.slice(0, 40)}`,
        summary: "Desk research + comparables + feasibility scan.",
        status: "RESEARCHING",
        parentIds: [hyp.id],
        why: "Gather evidence before committing to experiments.",
        evidence: ["Comparable products", "Public benchmarks", "Cost model sketch"],
        experimentIds: [],
        x: hyp.x,
        y: hyp.y + 140,
        score: computeScore({
          potential: hyp.score.potential,
          evidence: 45,
          confidence: 40,
          feasibility: hyp.score.feasibility,
          novelty: hyp.score.novelty,
        }),
      },
      hyp.id
    );
    next = updateNode(next, hyp.id, {
      status: "RESEARCHING",
      evidence: [...hyp.evidence, "Research branch opened"],
    });
    // Surface a latent assumption under research
    const assumeId = uid("asm");
    next = addNode(
      next,
      {
        id: assumeId,
        kind: "ASSUMPTION",
        title: `Assumption: “${hyp.title}” is urgent for early adopters`,
        summary: "Unstated belief that must hold for this hypothesis to matter.",
        status: "NEW",
        parentIds: [id],
        why: "Research exposed a load-bearing belief that was not yet tested.",
        evidence: ["Inferred from research framing"],
        experimentIds: [],
        x: hyp.x + 120,
        y: hyp.y + 200,
        score: computeScore({ potential: 70, evidence: 20, confidence: 35, feasibility: 60, novelty: 40 }),
      },
      id
    );
    const wm = {
      ...next.worldModel,
      assumptions: [...new Set([...next.worldModel.assumptions, `Urgency of ${hyp.title}`])],
      knowns: [...new Set([...next.worldModel.knowns, `Research opened for ${hyp.title}`])],
      lastUpdatedAt: new Date().toISOString(),
    };
    return { ...next, worldModel: wm };
  }

  detectDiscoveries(map: OmniMap, onlyKinds?: ShadowKind[]): OmniMap {
    const topic = topicFromGoal(map.goal);
    const goal = map.nodes.find((n) => n.kind === "GOAL");
    if (!goal) return map;
    // Knowledge Core: do not invent shadow noise. Demo may seed a small set;
    // live path should pass onlyKinds from model output that has real evidence.
    const defaultKinds: ShadowKind[] = map.demoMode
      ? (["HIDDEN_ASSUMPTION", "ALTERNATIVE_PATH", "MISSING_EVIDENCE", "HIGH_INFO_EXPERIMENT"] as ShadowKind[])
      : [];
    const kinds = (onlyKinds?.length ? onlyKinds : defaultKinds).filter((k) => k in SHADOW_META);
    if (!kinds.length) return map;
    let next = map;
    const discoveries: OmniDiscovery[] = [...map.discoveries];
    kinds.forEach((kind, i) => {
      if (discoveries.some((d) => d.kind === kind)) return;
      const meta = SHADOW_META[kind];
      const nodeId = uid("disc");
      const discovery: OmniDiscovery = {
        id: uid("sh"),
        kind,
        title: meta.title(topic),
        summary: `Shadow analysis surfaced a ${kind.replaceAll("_", " ").toLowerCase()}.`,
        evidence: map.demoMode
          ? ["Demo pattern library", "Goal structure"]
          : ["Live analysis"],
        confidence: meta.confidence,
        potential: meta.potential,
        nextAction: meta.next,
        relatedNodeIds: [goal.id],
        nodeId,
      };
      discoveries.push(discovery);
      const pos = placeAround(goal.x - 280, goal.y + 40, i, kinds.length, 200);
      next = addNode(
        next,
        {
          id: nodeId,
          kind: "DISCOVERY",
          title: discovery.title.slice(0, 72),
          summary: `${discovery.summary} Next: ${discovery.nextAction}`,
          status: "PROMISING",
          parentIds: [goal.id],
          why: "SHADOW ANALYSIS — what nobody thought to ask yet.",
          evidence: discovery.evidence,
          experimentIds: [],
          discoveryKind: kind,
          x: pos.x,
          y: pos.y,
          score: computeScore({
            potential: discovery.potential,
            evidence: 35,
            confidence: discovery.confidence,
            feasibility: 50,
            novelty: 85,
          }),
        },
        goal.id,
        "shadow"
      );
    });
    const wm: WorldModel = {
      ...next.worldModel,
      openQuestions: [
        ...new Set([...next.worldModel.openQuestions, ...discoveries.map((d) => d.nextAction)]),
      ],
      unknowns: [...new Set([...next.worldModel.unknowns, "Shadow risks not yet measured"])],
      contradictions: [
        ...new Set([
          ...next.worldModel.contradictions,
          ...discoveries.filter((d) => d.kind === "CONTRADICTION").map((d) => d.title),
        ]),
      ],
      lastUpdatedAt: new Date().toISOString(),
    };
    return { ...next, discoveries, worldModel: wm };
  }

  createExperiment(map: OmniMap, hypothesisId: string): OmniMap {
    const hyp = map.nodes.find((n) => n.id === hypothesisId);
    if (!hyp) return map;
    const expId = uid("exp");
    const nodeId = uid("expn");
    const experiment: OmniExperiment = {
      id: expId,
      hypothesisId,
      objective: `Validate signal for “${hyp.title.slice(0, 48)}”.`,
      method: "Smoke test / interviews / prototype (DEMO)",
      expectedResult: "Clear pull signal (≥30% intent).",
      actualResult: "",
      status: "TESTING",
      evidence: [],
    };
    let next = addNode(
      map,
      {
        id: nodeId,
        kind: "EXPERIMENT",
        title: `Experiment: ${hyp.title.slice(0, 36)}`,
        summary: experiment.method,
        status: "TESTING",
        parentIds: [hyp.id],
        why: `Experiment designed to stress-test “${hyp.title}”.`,
        evidence: ["Experiment brief drafted"],
        experimentIds: [expId],
        x: hyp.x,
        y: hyp.y + 240,
        score: hyp.score,
      },
      hyp.id
    );
    next = updateNode(next, hyp.id, {
      status: "TESTING",
      experimentIds: [...hyp.experimentIds, expId],
    });
    return { ...next, experiments: [...next.experiments, experiment] };
  }

  evaluateExperiment(
    map: OmniMap,
    experimentId: string,
    outcome: "success" | "mixed" | "fail" = "success"
  ): OmniMap {
    const experiment = map.experiments.find((e) => e.id === experimentId);
    if (!experiment) return map;
    const hyp = map.nodes.find((n) => n.id === experiment.hypothesisId);
    const expNode = map.nodes.find(
      (n) => n.kind === "EXPERIMENT" && n.experimentIds.includes(experimentId)
    );
    if (!hyp || !expNode) return map;

    const actual =
      outcome === "success"
        ? "Strong intent; users asked for waitlist."
        : outcome === "mixed"
          ? "Interest present but activation friction high."
          : "Weak intent; problem not urgent enough.";
    const evidence =
      outcome === "fail"
        ? ["Interview notes: low urgency", "CTR below threshold"]
        : ["User quotes", "Conversion metrics"];
    const status: OmniStatus =
      outcome === "fail" ? "REJECTED" : outcome === "mixed" ? "TESTING" : "VALIDATED";
    const newScore = scoreFromExperimentOutcome(hyp.score, outcome);

    const experiments = map.experiments.map((e) =>
      e.id === experimentId
        ? { ...e, actualResult: actual, status, evidence }
        : e
    );
    let next: OmniMap = { ...map, experiments };
    next = updateNode(next, expNode.id, {
      status,
      evidence,
      score: newScore,
      summary: actual,
    });
    const resultId = uid("resu");
    next = addNode(
      next,
      {
        id: resultId,
        kind: "RESULT",
        title: outcome === "fail" ? "Weak signal" : outcome === "mixed" ? "Mixed signal" : "Validated signal",
        summary: actual,
        status,
        parentIds: [expNode.id],
        why: "Experiment outcome recorded as evidence — model must update.",
        evidence,
        experimentIds: [experimentId],
        rejectedReason: outcome === "fail" ? "Insufficient urgency / weak conversion evidence." : undefined,
        x: expNode.x,
        y: expNode.y + 120,
        score: newScore,
      },
      expNode.id
    );
    next = updateNode(next, hyp.id, {
      score: newScore,
      status: statusFromScore(newScore, outcome === "fail" ? "REJECTED" : undefined),
      evidence: [...hyp.evidence, ...evidence],
      rejectedReason:
        outcome === "fail" ? "Experiment failed: weak demand signal and low urgency." : hyp.rejectedReason,
      why:
        outcome === "fail"
          ? `${hyp.why} Rejected after experiment evidence.`
          : `${hyp.why} Strengthened by experiment evidence.`,
    });
    next = this.updateWorldModel(next, {
      knowns: [`Experiment on ${hyp.title}: ${outcome}`],
      unknowns: outcome === "success" ? [] : ["What activation friction remains?"],
      contradictions: outcome === "fail" ? [`Hypothesis “${hyp.title}” vs observed demand`] : [],
    });
    return this.rankPaths(next);
  }

  createCrossover(map: OmniMap, aId: string, bId: string): OmniMap | null {
    const a = map.nodes.find((n) => n.id === aId);
    const b = map.nodes.find((n) => n.id === bId);
    if (!a || !b || aId === bId) return null;
    const id = uid("cross");
    const title = `${a.title.split(/[\s—-]+/).slice(0, 3).join(" ")} × ${b.title.split(/[\s—-]+/).slice(0, 3).join(" ")}`;
    const score = computeScore({
      potential: (a.score.potential + b.score.potential) / 2 + 8,
      evidence: (a.score.evidence + b.score.evidence) / 2,
      confidence: (a.score.confidence + b.score.confidence) / 2,
      feasibility: (a.score.feasibility + b.score.feasibility) / 2 - 4,
      novelty: Math.max(a.score.novelty, b.score.novelty) + 12,
    });
    let next = addNode(
      map,
      {
        id,
        kind: "CROSSOVER",
        title: title.slice(0, 90),
        summary: `Synthesis of “${a.title}” and “${b.title}”.`,
        status: "PROMISING",
        parentIds: [aId, bId],
        why: `Crossover keeps links to both parents for traceable exploration.`,
        evidence: [...a.evidence.slice(0, 2), ...b.evidence.slice(0, 2), "Crossover synthesis"],
        experimentIds: [],
        x: (a.x + b.x) / 2,
        y: (a.y + b.y) / 2 + 140,
        score,
      },
      aId,
      "crossover"
    );
    next = {
      ...next,
      edges: [...next.edges, { id: uid("edge"), from: bId, to: id, kind: "crossover", label: "crossover" }],
    };
    // Child hypothesis ready for experiment
    const hypId = uid("hyp");
    next = addNode(
      next,
      {
        id: hypId,
        kind: "HYPOTHESIS",
        title: `Combined path: ${title.slice(0, 48)}`,
        summary: "New hypothesis spawned from crossover — ready to experiment.",
        status: "PROMISING",
        parentIds: [id],
        why: `Emerged from crossover “${title}”.`,
        evidence: next.nodes.find((n) => n.id === id)?.evidence ?? [],
        experimentIds: [],
        x: (a.x + b.x) / 2,
        y: (a.y + b.y) / 2 + 260,
        score,
      },
      id
    );
    return this.rankPaths(next);
  }

  /** WHAT IF? on an assumption — spawn a real alternate branch. */
  whatIf(map: OmniMap, assumptionId: string): OmniMap | null {
    const asm = map.nodes.find((n) => n.id === assumptionId && n.kind === "ASSUMPTION");
    if (!asm) return null;
    const branchId = uid("hyp");
    const riskId = uid("hyp");
    let next = addNode(
      map,
      {
        id: branchId,
        kind: "HYPOTHESIS",
        title: `WHAT IF false: ${asm.title.replace(/^Assumption:\s*/i, "").slice(0, 50)}`,
        summary: "Counterfactual branch — explore the world where the assumption fails.",
        status: "NEW",
        parentIds: [asm.id],
        why: `WHAT IF? flipped “${asm.title}” and forced an alternate path.`,
        evidence: [...asm.evidence, "Counterfactual branch"],
        experimentIds: [],
        whatIfOf: asm.id,
        x: asm.x - 160,
        y: asm.y + 140,
        score: computeScore({
          potential: asm.score.potential + 5,
          evidence: asm.score.evidence,
          confidence: Math.max(20, asm.score.confidence - 15),
          feasibility: asm.score.feasibility - 5,
          novelty: 88,
        }),
      },
      asm.id,
      "whatif"
    );
    next = addNode(
      next,
      {
        id: riskId,
        kind: "HYPOTHESIS",
        title: "Risk: wasted build if assumption fails",
        summary: "Explicit downside path with experiments that would detect failure early.",
        status: "NEW",
        parentIds: [branchId],
        why: "WHAT IF? also surfaces risks and high-information tests.",
        evidence: ["Counterfactual risk register"],
        experimentIds: [],
        whatIfOf: asm.id,
        x: asm.x - 160,
        y: asm.y + 260,
        score: computeScore({ potential: 55, evidence: 25, confidence: 40, feasibility: 70, novelty: 60 }),
      },
      branchId,
      "whatif"
    );
    next = {
      ...next,
      worldModel: {
        ...next.worldModel,
        openQuestions: [
          ...new Set([...next.worldModel.openQuestions, `What if “${asm.title}” is false?`]),
        ],
        lastUpdatedAt: new Date().toISOString(),
      },
    };
    return next;
  }

  updateWorldModel(
    map: OmniMap,
    patch: Partial<Pick<WorldModel, "knowns" | "unknowns" | "assumptions" | "contradictions" | "openQuestions">>
  ): OmniMap {
    const wm = map.worldModel;
    return {
      ...map,
      worldModel: {
        ...wm,
        knowns: [...new Set([...wm.knowns, ...(patch.knowns ?? [])])],
        unknowns: [...new Set([...wm.unknowns, ...(patch.unknowns ?? [])])],
        assumptions: [...new Set([...wm.assumptions, ...(patch.assumptions ?? [])])],
        contradictions: [...new Set([...wm.contradictions, ...(patch.contradictions ?? [])])],
        openQuestions: [...new Set([...wm.openQuestions, ...(patch.openQuestions ?? [])])],
        lastUpdatedAt: new Date().toISOString(),
      },
    };
  }

  rankPaths(map: OmniMap): OmniMap {
    // Drop previous BEST_PATH markers (keep history nodes of other kinds)
    let next: OmniMap = {
      ...map,
      nodes: map.nodes.filter((n) => n.kind !== "BEST_PATH"),
      edges: map.edges.filter((e) => e.kind !== "best"),
    };
    const ranked = [...next.nodes]
      .filter(
        (n) =>
          (n.kind === "HYPOTHESIS" || n.kind === "CROSSOVER" || n.kind === "DISCOVERY") &&
          n.status !== "REJECTED"
      )
      .sort((a, b) => b.score.overall - a.score.overall)
      .slice(0, 3);
    ranked.forEach((n, i) => {
      const id = uid("best");
      next = addNode(
        next,
        {
          id,
          kind: "BEST_PATH",
          title: `Best path #${i + 1}`,
          summary: n.title,
          status: "PROMISING",
          parentIds: [n.id],
          why: `Ranked #${i + 1} by overall=${n.score.overall} (potential ${n.score.potential}, evidence ${n.score.evidence}, confidence ${n.score.confidence}, feasibility ${n.score.feasibility}, novelty ${n.score.novelty}). Based on recorded evidence/assumptions — not hidden chain-of-thought.`,
          evidence: n.evidence,
          experimentIds: n.experimentIds,
          x: n.x + 200,
          y: n.y - 40 + i * 24,
          score: n.score,
        },
        n.id,
        "best"
      );
    });
    return next;
  }
}

export const realityEngine = new ExplorationEngine();

/** Progressive DEMO explore pipeline using ExplorationEngine methods. */
export function buildExploreSteps(goal: string): Array<(map: OmniMap) => OmniMap> {
  const engine = realityEngine;
  let hypIds: string[] = [];
  let expIds: string[] = [];

  return [
    (map) => engine.generateHypotheses(map, undefined, 3),
    (map) => {
      hypIds = map.nodes.filter((n) => n.kind === "HYPOTHESIS").map((n) => n.id);
      let next = map;
      hypIds.slice(0, 3).forEach((id) => {
        next = engine.researchHypothesis(next, id);
      });
      return next;
    },
    (map) => engine.detectDiscoveries(map),
    (map) => {
      let next = map;
      expIds = [];
      hypIds.slice(0, 3).forEach((id) => {
        next = engine.createExperiment(next, id);
        const last = next.experiments[next.experiments.length - 1];
        if (last) expIds.push(last.id);
      });
      return next;
    },
    (map) => {
      let next = map;
      expIds.forEach((id, i) => {
        const outcome: "success" | "mixed" | "fail" = i === 1 ? "fail" : i === 2 ? "mixed" : "success";
        next = engine.evaluateExperiment(next, id, outcome);
      });
      return next;
    },
    (map) => {
      const top = [...map.nodes]
        .filter((n) => n.kind === "HYPOTHESIS" && n.status !== "REJECTED")
        .sort((a, b) => b.score.overall - a.score.overall)
        .slice(0, 2);
      if (top.length < 2) return map;
      return engine.createCrossover(map, top[0].id, top[1].id) ?? map;
    },
    (map) => engine.rankPaths({ ...map, exploring: false }),
  ];
}

export function createEmptyMap(goal: string): OmniMap {
  return realityEngine.createSession(goal, { demoMode: false });
}

export function createCrossover(map: OmniMap, aId: string, bId: string): OmniMap | null {
  return realityEngine.createCrossover(map, aId, bId);
}

export function kindColor(kind: OmniNodeKind): string {
  switch (kind) {
    case "GOAL":
      return "var(--nexa-violet)";
    case "HYPOTHESIS":
      return "var(--mode-agent)";
    case "RESEARCH":
      return "var(--nexa-cyan)";
    case "ASSUMPTION":
      return "var(--mode-agent)";
    case "DISCOVERY":
      return "oklch(0.75 0.16 85)";
    case "EXPERIMENT":
      return "var(--mode-research)";
    case "RESULT":
      return "var(--mode-code)";
    case "CROSSOVER":
      return "var(--mode-create)";
    case "BEST_PATH":
      return "var(--mode-vision)";
  }
}
