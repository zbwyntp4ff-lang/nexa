/** NEXA Reality Engine / Omniverse — Live Exploration types. */

export type OmniNodeKind =
  | "GOAL"
  | "HYPOTHESIS"
  | "RESEARCH"
  | "ASSUMPTION"
  | "DISCOVERY"
  | "EXPERIMENT"
  | "RESULT"
  | "CROSSOVER"
  | "BEST_PATH";

export type OmniStatus =
  | "NEW"
  | "RESEARCHING"
  | "TESTING"
  | "VALIDATED"
  | "PROMISING"
  | "REJECTED";

export type ShadowKind =
  | "HIDDEN_ASSUMPTION"
  | "ALTERNATIVE_PATH"
  | "UNEXPECTED_CONNECTION"
  | "MISSING_EVIDENCE"
  | "HIGH_INFO_EXPERIMENT"
  | "CONTRADICTION"
  | "BLIND_SPOT"
  /** FORGE — useful combination of ideas (hypothesis until evidenced). */
  | "FORGE_COMBINATION"
  /** BREAKTHROUGH — distant non-obvious link (hypothesis until validated). */
  | "BREAKTHROUGH_LINK";

export interface OmniScore {
  potential: number;
  evidence: number;
  confidence: number;
  feasibility: number;
  novelty: number;
  overall: number;
}

export interface OmniDiscovery {
  id: string;
  kind: ShadowKind;
  title: string;
  summary: string;
  evidence: string[];
  confidence: number;
  potential: number;
  nextAction: string;
  relatedNodeIds: string[];
  nodeId?: string;
}

export interface OmniExperiment {
  id: string;
  hypothesisId: string;
  objective: string;
  method: string;
  expectedResult: string;
  actualResult: string;
  status: OmniStatus;
  evidence: string[];
}

export interface OmniNode {
  id: string;
  kind: OmniNodeKind;
  title: string;
  summary: string;
  status: OmniStatus;
  score: OmniScore;
  parentIds: string[];
  /** Why this path appeared / was kept or rejected (evidence-based, not CoT). */
  why: string;
  evidence: string[];
  experimentIds: string[];
  rejectedReason?: string;
  /** WHAT IF source assumption id, if this branch was spawned by counterfactual. */
  whatIfOf?: string;
  discoveryKind?: ShadowKind;
  x: number;
  y: number;
  expanded: boolean;
  bornAt: number;
  visible: boolean;
}

export interface OmniEdge {
  id: string;
  from: string;
  to: string;
  label?: string;
  kind: "flow" | "crossover" | "best" | "whatif" | "shadow";
}

/** Explicit living model of the problem — updated after experiments. */
export interface WorldModel {
  goal: string;
  knowns: string[];
  unknowns: string[];
  assumptions: string[];
  contradictions: string[];
  openQuestions: string[];
  lastUpdatedAt: string;
}

export interface OmniMap {
  id: string;
  goal: string;
  createdAt: string;
  exploring: boolean;
  /** Explicit DEMO MODE — synthetic exploration, never mixed with live AI. */
  demoMode: boolean;
  worldModel: WorldModel;
  nodes: OmniNode[];
  edges: OmniEdge[];
  experiments: OmniExperiment[];
  discoveries: OmniDiscovery[];
}
