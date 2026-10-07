import { describe, expect, it } from "vitest";
import { computeScore, scoreFromExperimentOutcome, statusFromScore } from "@/lib/omniverse/scoring";
import {
  buildExploreSteps,
  createCrossover,
  createEmptyMap,
  realityEngine,
} from "@/lib/omniverse/explore-engine";

describe("omniverse scoring", () => {
  it("computes overall from weighted factors", () => {
    const s = computeScore({
      potential: 80,
      evidence: 70,
      confidence: 60,
      feasibility: 50,
      novelty: 90,
    });
    expect(s.overall).toBeGreaterThan(60);
    expect(s.overall).toBeLessThanOrEqual(100);
  });

  it("boosts score on successful experiment", () => {
    const base = computeScore({ potential: 50, evidence: 40, confidence: 40, feasibility: 50, novelty: 50 });
    const next = scoreFromExperimentOutcome(base, "success");
    expect(next.evidence).toBeGreaterThan(base.evidence);
    expect(next.overall).toBeGreaterThan(base.overall);
  });

  it("maps low scores to REJECTED", () => {
    expect(
      statusFromScore(computeScore({ potential: 10, evidence: 10, confidence: 10, feasibility: 10, novelty: 10 }))
    ).toBe("REJECTED");
  });
});

describe("ExplorationEngine / Reality Engine", () => {
  it("creates a DEMO session with world model", () => {
    const map = realityEngine.createSession("Create a successful AI product", { demoMode: true });
    expect(map.demoMode).toBe(true);
    expect(map.nodes[0].kind).toBe("GOAL");
    expect(map.worldModel.goal).toContain("successful");
    expect(map.discoveries).toEqual([]);
  });

  it("runs DEMO explore: shadow, experiments, crossover, best paths", () => {
    let map = realityEngine.createSession("Create a successful AI product", { demoMode: true });
    for (const step of buildExploreSteps(map.goal)) {
      map = step(map);
    }
    expect(map.demoMode).toBe(true);
    expect(map.nodes.some((n) => n.kind === "ASSUMPTION")).toBe(true);
    expect(map.nodes.some((n) => n.kind === "DISCOVERY")).toBe(true);
    expect(map.discoveries.length).toBeGreaterThan(0);
    expect(map.discoveries.every((d) => d.nextAction && d.evidence.length)).toBe(true);
    expect(map.nodes.some((n) => n.status === "REJECTED")).toBe(true);
    expect(map.nodes.some((n) => n.kind === "CROSSOVER")).toBe(true);
    expect(map.nodes.some((n) => n.kind === "BEST_PATH")).toBe(true);
    expect(map.experiments.length).toBeGreaterThan(0);
    expect(map.worldModel.knowns.length).toBeGreaterThan(1);
  });

  it("WHAT IF? spawns alternate branch from assumption", () => {
    let map = createEmptyMap("Goal");
    map = realityEngine.generateHypotheses(map, undefined, 1);
    const hyp = map.nodes.find((n) => n.kind === "HYPOTHESIS")!;
    map = realityEngine.researchHypothesis(map, hyp.id);
    const asm = map.nodes.find((n) => n.kind === "ASSUMPTION")!;
    const next = realityEngine.whatIf(map, asm.id);
    expect(next).not.toBeNull();
    expect(next!.nodes.some((n) => n.whatIfOf === asm.id)).toBe(true);
  });

  it("experiment updates model and re-ranks", () => {
    let map = createEmptyMap("Goal");
    map = realityEngine.generateHypotheses(map, undefined, 1);
    const hyp = map.nodes.find((n) => n.kind === "HYPOTHESIS")!;
    map = realityEngine.createExperiment(map, hyp.id);
    const exp = map.experiments[0];
    const before = hyp.score.overall;
    map = realityEngine.evaluateExperiment(map, exp.id, "success");
    const updated = map.nodes.find((n) => n.id === hyp.id)!;
    expect(updated.score.overall).toBeGreaterThan(before);
    expect(map.nodes.some((n) => n.kind === "RESULT")).toBe(true);
    expect(map.nodes.some((n) => n.kind === "BEST_PATH")).toBe(true);
  });

  it("crossover keeps both parents", () => {
    let map = createEmptyMap("Goal");
    for (const step of buildExploreSteps(map.goal).slice(0, 1)) map = step(map);
    const hyps = map.nodes.filter((n) => n.kind === "HYPOTHESIS").slice(0, 2);
    expect(hyps.length).toBe(2);
    const next = createCrossover(map, hyps[0].id, hyps[1].id);
    expect(next).not.toBeNull();
    const cross = next!.nodes.find((n) => n.kind === "CROSSOVER")!;
    expect(cross.parentIds).toEqual(expect.arrayContaining([hyps[0].id, hyps[1].id]));
  });
});
