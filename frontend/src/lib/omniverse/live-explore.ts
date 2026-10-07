/**
 * Live Reality Engine adapter — uses the existing NEXA chat AI abstraction.
 * Never mixes DEMO synthetic data into this path.
 */
import { sendChat } from "@/lib/api";
import { realityEngine } from "@/lib/omniverse/explore-engine";
import { computeScore } from "@/lib/omniverse/scoring";
import type { OmniMap, OmniNode, ShadowKind } from "@/lib/omniverse/types";

function uid(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 9)}`;
}

function extractJson(text: string): unknown {
  const trimmed = text.trim();
  try {
    return JSON.parse(trimmed);
  } catch {
    /* fall through */
  }
  const fence = trimmed.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fence) {
    try {
      return JSON.parse(fence[1].trim());
    } catch {
      /* fall through */
    }
  }
  const start = trimmed.indexOf("{");
  const end = trimmed.lastIndexOf("}");
  if (start >= 0 && end > start) {
    return JSON.parse(trimmed.slice(start, end + 1));
  }
  const a0 = trimmed.indexOf("[");
  const a1 = trimmed.lastIndexOf("]");
  if (a0 >= 0 && a1 > a0) {
    return JSON.parse(trimmed.slice(a0, a1 + 1));
  }
  throw new Error("Model did not return valid JSON.");
}

async function askJson<T>(prompt: string, signal?: AbortSignal): Promise<T> {
  const response = await sendChat(prompt, [], signal, { task: "research" });
  return extractJson(response.message) as T;
}

function placeAround(cx: number, cy: number, index: number, total: number, radius: number) {
  const angle = -Math.PI / 2 + (index / Math.max(total, 1)) * Math.PI * 2;
  return { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius };
}

function addNode(
  map: OmniMap,
  node: OmniNode,
  fromId?: string,
  edgeKind: "flow" | "crossover" | "best" | "whatif" | "shadow" = "flow"
): OmniMap {
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

type HypoOut = {
  title: string;
  summary: string;
  why: string;
  evidence: string[];
  potential: number;
  confidence: number;
  feasibility: number;
  novelty: number;
};

type ResearchOut = {
  research_title: string;
  research_summary: string;
  evidence: string[];
  assumption_title: string;
  assumption_summary: string;
};

type ShadowOut = {
  discoveries: Array<{
    kind: ShadowKind;
    title: string;
    summary: string;
    evidence: string[];
    confidence: number;
    potential: number;
    next_action: string;
  }>;
};

type ExperimentOut = {
  objective: string;
  method: string;
  expected: string;
  outcome: "success" | "mixed" | "fail";
  actual: string;
  evidence: string[];
};

type CrossoverOut = {
  title: string;
  summary: string;
  why: string;
  child_hypothesis: string;
};

export type LiveExploreProgress = (phase: string, map: OmniMap) => void;

/**
 * Full live exploration against the configured AI provider.
 * Sets demoMode=false on the session.
 */
export async function runLiveExplore(
  goal: string,
  onProgress?: LiveExploreProgress,
  signal?: AbortSignal
): Promise<OmniMap> {
  let map = realityEngine.createSession(goal, { demoMode: false });
  onProgress?.("WORLD MODEL", map);

  const goalNode = map.nodes.find((n) => n.kind === "GOAL")!;
  const hyps = await askJson<{ hypotheses: HypoOut[] }>(
    `You are NEXA Reality Engine. Goal: "${map.goal}".
Return JSON only:
{"hypotheses":[{"title":"...","summary":"...","why":"...","evidence":["..."],"potential":0-100,"confidence":0-100,"feasibility":0-100,"novelty":0-100}]}
Give exactly 3 distinct, testable hypotheses. No chain-of-thought outside JSON.`,
    signal
  );

  const hypIds: string[] = [];
  (hyps.hypotheses ?? []).slice(0, 3).forEach((h, i) => {
    const id = uid("hyp");
    hypIds.push(id);
    const pos = placeAround(goalNode.x, goalNode.y, i, 3, 220);
    map = addNode(
      map,
      {
        id,
        kind: "HYPOTHESIS",
        title: (h.title || `Hypothesis ${i + 1}`).slice(0, 90),
        summary: h.summary || "",
        status: "NEW",
        score: computeScore({
          potential: h.potential ?? 60,
          evidence: 25,
          confidence: h.confidence ?? 40,
          feasibility: h.feasibility ?? 50,
          novelty: h.novelty ?? 55,
        }),
        parentIds: [goalNode.id],
        why: h.why || "Generated from goal by live Reality Engine.",
        evidence: h.evidence?.length ? h.evidence : ["AI hypothesis generation"],
        experimentIds: [],
        x: pos.x,
        y: pos.y,
        expanded: true,
        bornAt: Date.now(),
        visible: true,
      },
      goalNode.id
    );
  });
  onProgress?.("HYPOTHESES", map);

  for (const hid of hypIds) {
    signal?.throwIfAborted?.();
    const hyp = map.nodes.find((n) => n.id === hid)!;
    const research = await askJson<ResearchOut>(
      `NEXA Reality Engine research step.
Goal: "${map.goal}"
Hypothesis: "${hyp.title}" — ${hyp.summary}
Return JSON only:
{"research_title":"...","research_summary":"...","evidence":["..."],"assumption_title":"...","assumption_summary":"..."}
Focus on what must be true and what is still unknown. No chain-of-thought outside JSON.`,
      signal
    );
    map = realityEngine.researchHypothesis(map, hid);
    // Replace last research + assumption content with live AI text
    const researchNode = [...map.nodes].reverse().find((n) => n.kind === "RESEARCH" && n.parentIds.includes(hid));
    const assumeNode = [...map.nodes].reverse().find((n) => n.kind === "ASSUMPTION");
    if (researchNode) {
      map = {
        ...map,
        nodes: map.nodes.map((n) =>
          n.id === researchNode.id
            ? {
                ...n,
                title: (research.research_title || n.title).slice(0, 90),
                summary: research.research_summary || n.summary,
                evidence: research.evidence?.length ? research.evidence : n.evidence,
                why: "Live research against the configured AI provider.",
              }
            : n
        ),
      };
    }
    if (assumeNode && research.assumption_title) {
      map = {
        ...map,
        nodes: map.nodes.map((n) =>
          n.id === assumeNode.id
            ? {
                ...n,
                title: research.assumption_title.slice(0, 90),
                summary: research.assumption_summary || n.summary,
                why: "Load-bearing assumption exposed by live research.",
              }
            : n
        ),
      };
    }
    onProgress?.("RESEARCH", map);
  }

  const shadow = await askJson<ShadowOut>(
    `NEXA Knowledge Core — SHADOW / FORGE / BREAKTHROUGH for goal "${map.goal}".
Hypotheses: ${map.nodes
      .filter((n) => n.kind === "HYPOTHESIS")
      .map((n) => n.title)
      .join(" | ")}
World unknowns: ${map.worldModel.unknowns.join("; ") || "none"}
Contradictions: ${map.worldModel.contradictions.join("; ") || "none"}
Return JSON only:
{"discoveries":[{"kind":"HIDDEN_ASSUMPTION|ALTERNATIVE_PATH|UNEXPECTED_CONNECTION|MISSING_EVIDENCE|HIGH_INFO_EXPERIMENT|CONTRADICTION|BLIND_SPOT|FORGE_COMBINATION|BREAKTHROUGH_LINK","title":"...","summary":"...","evidence":["..."],"confidence":0-100,"potential":0-100,"next_action":"..."}]}
Rules from Knowledge Core:
- Only include discoveries with real evidence from the goal/hypotheses — omit empty kinds.
- Do NOT invent problems to fill a quota.
- FORGE_COMBINATION = useful idea merge (mark as hypothesis).
- BREAKTHROUGH_LINK = distant link (hypothesis until validated).
- Label weak claims as hypothesis in summary. No chain-of-thought outside JSON.`,
    signal
  );

  const live = (shadow.discoveries ?? []).filter(
    (d) => Array.isArray(d.evidence) && d.evidence.length > 0 && d.title?.trim()
  );
  // Seed only kinds the model actually found — never invent the full catalog.
  map = realityEngine.detectDiscoveries(
    map,
    live.map((d) => d.kind)
  );
  live.forEach((d) => {
    const node = map.nodes.find((n) => n.kind === "DISCOVERY" && n.discoveryKind === d.kind);
    if (!node) return;
    map = {
      ...map,
      nodes: map.nodes.map((n) =>
        n.id === node.id
          ? {
              ...n,
              title: d.title.slice(0, 90),
              summary: `${d.summary} Next: ${d.next_action}`,
              evidence: d.evidence?.length ? d.evidence : n.evidence,
              score: computeScore({
                potential: d.potential ?? n.score.potential,
                evidence: 40,
                confidence: d.confidence ?? n.score.confidence,
                feasibility: 50,
                novelty: 85,
              }),
              why: "SHADOW ANALYSIS from live AI — what nobody thought to ask.",
            }
          : n
      ),
      discoveries: map.discoveries.map((x) =>
        x.kind === d.kind
          ? {
              ...x,
              title: d.title,
              summary: d.summary,
              evidence: d.evidence ?? x.evidence,
              confidence: d.confidence ?? x.confidence,
              potential: d.potential ?? x.potential,
              nextAction: d.next_action || x.nextAction,
            }
          : x
      ),
    };
  });
  onProgress?.("SHADOW ANALYSIS", map);

  const expIds: string[] = [];
  for (const hid of hypIds.slice(0, 3)) {
    signal?.throwIfAborted?.();
    const hyp = map.nodes.find((n) => n.id === hid)!;
    const plan = await askJson<ExperimentOut>(
      `Design and evaluate one experiment for hypothesis "${hyp.title}" under goal "${map.goal}".
Return JSON only:
{"objective":"...","method":"...","expected":"...","outcome":"success|mixed|fail","actual":"...","evidence":["..."]}
Pick a realistic outcome based on the hypothesis quality. No chain-of-thought outside JSON.`,
      signal
    );
    map = realityEngine.createExperiment(map, hid);
    const exp = map.experiments[map.experiments.length - 1];
    if (!exp) continue;
    expIds.push(exp.id);
    map = {
      ...map,
      experiments: map.experiments.map((e) =>
        e.id === exp.id
          ? {
              ...e,
              objective: plan.objective || e.objective,
              method: plan.method || e.method,
              expectedResult: plan.expected || e.expectedResult,
            }
          : e
      ),
    };
    const outcome = plan.outcome === "fail" || plan.outcome === "mixed" ? plan.outcome : "success";
    map = realityEngine.evaluateExperiment(map, exp.id, outcome);
    // Overlay AI actual/evidence on latest result
    const result = [...map.nodes].reverse().find((n) => n.kind === "RESULT");
    if (result && plan.actual) {
      map = {
        ...map,
        nodes: map.nodes.map((n) =>
          n.id === result.id
            ? { ...n, summary: plan.actual, evidence: plan.evidence?.length ? plan.evidence : n.evidence }
            : n
        ),
        experiments: map.experiments.map((e) =>
          e.id === exp.id
            ? {
                ...e,
                actualResult: plan.actual || e.actualResult,
                evidence: plan.evidence?.length ? plan.evidence : e.evidence,
              }
            : e
        ),
      };
    }
    onProgress?.("EXPERIMENTS", map);
  }

  const top = [...map.nodes]
    .filter((n) => n.kind === "HYPOTHESIS" && n.status !== "REJECTED")
    .sort((a, b) => b.score.overall - a.score.overall)
    .slice(0, 2);
  if (top.length === 2) {
    const cross = await askJson<CrossoverOut>(
      `Create a CROSSOVER of:
A: "${top[0].title}" — ${top[0].summary}
B: "${top[1].title}" — ${top[1].summary}
Goal: "${map.goal}"
Return JSON only:
{"title":"...","summary":"...","why":"...","child_hypothesis":"..."}`,
      signal
    );
    const next = realityEngine.createCrossover(map, top[0].id, top[1].id);
    if (next) {
      map = next;
      const crossNode = map.nodes.find((n) => n.kind === "CROSSOVER");
      if (crossNode) {
        map = {
          ...map,
          nodes: map.nodes.map((n) => {
            if (n.id === crossNode.id) {
              return {
                ...n,
                title: (cross.title || n.title).slice(0, 90),
                summary: cross.summary || n.summary,
                why: cross.why || n.why,
              };
            }
            if (n.kind === "HYPOTHESIS" && n.parentIds.includes(crossNode.id) && cross.child_hypothesis) {
              return { ...n, title: cross.child_hypothesis.slice(0, 90) };
            }
            return n;
          }),
        };
      }
    }
    onProgress?.("CROSSOVER", map);
  }

  map = realityEngine.rankPaths({ ...map, exploring: false, demoMode: false });
  onProgress?.("BEST PATHS", map);
  return { ...map, demoMode: false, exploring: false };
}
