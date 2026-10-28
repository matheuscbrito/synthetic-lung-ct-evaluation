import { expect, test } from "vitest";
import type { Experiment } from "../contract/types";
import { realBundle } from "../fixtures";
import { filterExperiments, lastScore, lineage, selectedId, trajectoryLayout, trajectoryPaths } from "./experiments";

const exps = realBundle.experiments!.experiments;
const scopes = realBundle.experiments!.scopes;
const byId = Object.fromEntries(exps.map(e => [e.id, e]));

const exp = (id: string, parent: string | null, scores: Record<string, number | null> = {}): Experiment => ({
  id,
  parent,
  change: id,
  outcome: { status: "review", label: "Review" },
  scores,
  is_best: false,
  note: null,
});

test("lineage of M12 on the real fixture runs from its root to M12", () => {
  const line = lineage(byId, "M12");
  expect(line[0]).toBe("M4");
  expect(line.slice(-1)[0]).toBe("M12");
  expect(line).toEqual(["M4", "M6", "M7", "M8", "M10", "M11", "M12"]);
});

test("lineage terminates on a two-node cycle", () => {
  const cyclic = { A: exp("A", "B"), B: exp("B", "A") };
  expect(lineage(cyclic, "A")).toEqual(["B", "A"]);
});

test("lineage of an unknown id is empty", () => {
  expect(lineage(byId, "nope")).toEqual([]);
});

test("lastScore takes the largest scope with a score, or null", () => {
  expect(lastScore(byId.M12, scopes)).toBe(byId.M12.scores["37"]);
  expect(lastScore(byId.M9, scopes)).toBeNull();
});

test("trajectoryPaths: best lineage, then the latest scored experiment outside it", () => {
  const paths = trajectoryPaths(exps, scopes);
  expect(paths).toHaveLength(2);
  expect(paths[0].slice(-1)[0]).toBe("M12");
  expect(paths[1].slice(-1)[0]).toBe("L9");
});

test("selectedId keeps a known id, else falls back to the best, else the last", () => {
  expect(selectedId(exps, "L1")).toBe("L1");
  expect(selectedId(exps, "missing")).toBe("M12");
  expect(selectedId(exps, undefined)).toBe("M12");
  expect(selectedId([exp("A", null), exp("B", null)], undefined)).toBe("B");
  expect(selectedId([], undefined)).toBeNull();
});

test("filterExperiments matches id, change, outcome label and note, ignoring case", () => {
  expect(filterExperiments(exps, "").length).toBe(exps.length);
  expect(filterExperiments(exps, "m12").map(e => e.id)).toEqual(["M12", "L9"]);
  expect(filterExperiments(exps, "superada").map(e => e.id)).toEqual(["L9"]);
  expect(filterExperiments(exps, "ETA 0,40").map(e => e.id)).toEqual(["M12"]);
  expect(filterExperiments(exps, "no such text")).toEqual([]);
});

test("trajectoryLayout keeps item order, skips unscored points and marks the goal", () => {
  const paths = trajectoryPaths(exps, scopes);
  const layout = trajectoryLayout(exps, paths, scopes, realBundle.experiments!.objective.goal, { width: 560, height: 190, left: 40, right: 60, top: 12, bottom: 26 });
  expect(layout.paths.map(p => p.map(q => q.id))).toEqual(paths);
  for (const path of layout.paths) {
    const xs = path.map(q => q.x);
    expect([...xs].sort((a, b) => a - b)).toEqual(xs);
  }
  expect(layout.goalY).not.toBeNull();
  expect(layout.ticks[0]).toBeLessThanOrEqual(0);
  expect(layout.ticks.slice(-1)[0]).toBeGreaterThanOrEqual(realBundle.experiments!.objective.goal!);
});
