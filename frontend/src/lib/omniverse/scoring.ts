import type { OmniScore, OmniStatus } from "./types";

function clamp(n: number, min = 0, max = 100): number {
  return Math.max(min, Math.min(max, Math.round(n)));
}

/** Simple scoring service for Omniverse hypotheses / paths. */
export function computeScore(input: {
  potential?: number;
  evidence?: number;
  confidence?: number;
  feasibility?: number;
  novelty?: number;
}): OmniScore {
  const potential = clamp(input.potential ?? 50);
  const evidence = clamp(input.evidence ?? 40);
  const confidence = clamp(input.confidence ?? 45);
  const feasibility = clamp(input.feasibility ?? 50);
  const novelty = clamp(input.novelty ?? 55);
  const overall = clamp(
    potential * 0.25 +
      evidence * 0.25 +
      confidence * 0.2 +
      feasibility * 0.15 +
      novelty * 0.15
  );
  return { potential, evidence, confidence, feasibility, novelty, overall };
}

export function scoreFromExperimentOutcome(
  base: OmniScore,
  outcome: "success" | "mixed" | "fail"
): OmniScore {
  if (outcome === "success") {
    return computeScore({
      potential: base.potential + 6,
      evidence: base.evidence + 18,
      confidence: base.confidence + 14,
      feasibility: base.feasibility + 8,
      novelty: base.novelty + 2,
    });
  }
  if (outcome === "mixed") {
    return computeScore({
      potential: base.potential + 2,
      evidence: base.evidence + 10,
      confidence: base.confidence + 4,
      feasibility: base.feasibility - 2,
      novelty: base.novelty,
    });
  }
  return computeScore({
    potential: base.potential - 8,
    evidence: base.evidence + 8,
    confidence: base.confidence - 12,
    feasibility: base.feasibility - 10,
    novelty: base.novelty - 4,
  });
}

export function statusFromScore(score: OmniScore, forced?: OmniStatus): OmniStatus {
  if (forced) return forced;
  if (score.overall >= 78) return "PROMISING";
  if (score.overall >= 62) return "VALIDATED";
  if (score.overall >= 48) return "TESTING";
  if (score.overall >= 35) return "RESEARCHING";
  if (score.overall < 28) return "REJECTED";
  return "NEW";
}

export function emptyScore(): OmniScore {
  return computeScore({});
}
