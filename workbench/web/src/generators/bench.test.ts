import { expect, test } from "vitest";
import type { BoardVersion, Schema, Transition } from "../contract/types";
import { realBundle, stressBundle } from "../fixtures";
import {
  axisStatuses,
  clearDifferences,
  defaultCurrent,
  filterTransitions,
  generatorTabs,
  orderTransitions,
  orderVersions,
  resultStatus,
  scoreText,
  transitionSummary,
} from "./bench";

const recount = (t: Transition[]) => ({
  worsened: t.filter(x => x.change === "worsened").length,
  improved: t.filter(x => x.change === "improved").length,
  becameApproved: t.filter(x => x.became_approved).length,
});

test("transitionSummary on the real noise transitions matches a recount of the fixture", () => {
  const t = realBundle.transitions.noise;
  const out = transitionSummary(t);
  expect(out).toEqual(recount(t));
  // sanity: the fixture has movement in every bucket
  expect(out.worsened).toBeGreaterThan(0);
  expect(out.improved).toBeGreaterThan(0);
  expect(out.becameApproved).toBeGreaterThan(0);
});

test("transitionSummary of an empty list is all zeros", () => {
  expect(transitionSummary([])).toEqual({ worsened: 0, improved: 0, becameApproved: 0 });
});

test("orderTransitions: worsened first (most severe after first), then improved, then unchanged; ties by id", () => {
  const schema = realBundle.schema;
  const t: Transition[] = [
    { id: "c", before: "review", after: "approved", change: "improved", became_approved: true },
    { id: "b", before: "approved", after: "review", change: "worsened", became_approved: false },
    { id: "z", before: "approved", after: "approved", change: "same", became_approved: false },
    { id: "a", before: "approved", after: "rejected", change: "worsened", became_approved: false },
    { id: "d", before: "approved", after: "review", change: "worsened", became_approved: false },
  ];
  expect(orderTransitions(t, schema).map(x => x.id)).toEqual(["a", "b", "d", "c", "z"]);
});

test("filterTransitions: all = changed only; improved, worsened and became-approved subsets", () => {
  const t = realBundle.transitions.noise;
  const c = recount(t);
  expect(filterTransitions(t, "all")).toHaveLength(c.worsened + c.improved);
  expect(filterTransitions(t, "improved")).toHaveLength(c.improved);
  expect(filterTransitions(t, "worsened")).toHaveLength(c.worsened);
  expect(filterTransitions(t, "became")).toHaveLength(c.becameApproved);
  expect(filterTransitions(t, "all").every(x => x.change !== "same")).toBe(true);
});

test("generatorTabs: Benchmark always; Optimizers and Notebook from addons", () => {
  expect(generatorTabs({ optimizers: true, experiments: true }).map(t => t.label)).toEqual([
    "Benchmark",
    "Optimizers",
    "Notebook",
  ]);
  expect(generatorTabs(stressBundle.schema.addons).map(t => t.value)).toEqual(
    ["bench", "runs", "exp"].filter(k => k === "bench" || (k === "runs" ? stressBundle.schema.addons.optimizers : stressBundle.schema.addons.experiments)),
  );
  expect(generatorTabs({ optimizers: false, experiments: false }).map(t => t.value)).toEqual(["bench"]);
});

test("defaultCurrent: route version when valid and not the baseline, else newest non-reference non-baseline", () => {
  const vs = realBundle.board.versions;
  const base = realBundle.schema.dataset.default_baseline;
  const others = vs.filter(v => !v.is_reference && v.name !== base);
  expect(defaultCurrent(vs, base, undefined)).toBe(others[others.length - 1].name);
  expect(defaultCurrent(vs, base, "missing")).toBe(others[others.length - 1].name);
  expect(defaultCurrent(vs, base, base)).toBe(others[others.length - 1].name);
  const ref = vs.find(v => v.is_reference)!.name;
  expect(defaultCurrent(vs, base, ref)).toBe(ref);
  // only the baseline left: no current version
  expect(defaultCurrent(vs.filter(v => v.name === base), base, undefined)).toBeUndefined();
});

test("orderVersions: baseline, then current, then the rest by label", () => {
  const b = realBundle;
  const base = b.schema.dataset.default_baseline;
  const vs = b.board.versions.map(v => ({ ...v, label: b.versions.find(x => x.name === v.name)?.label ?? v.name }));
  const cur = defaultCurrent(vs, base, b.current)!;
  const out = orderVersions(vs, base, cur);
  expect(out.map(v => v.name).slice(0, 2)).toEqual([base, cur]);
  const rest = out.slice(2).map(v => v.label);
  expect(rest).toEqual([...rest].sort());
  expect(out).toHaveLength(vs.length);
  // without a current version: baseline first, the rest by label
  const noCur = orderVersions(vs, base);
  expect(noCur[0].name).toBe(base);
  expect(noCur.slice(1).map(v => v.label)).toEqual(noCur.slice(1).map(v => v.label).sort());
});

test("axisStatuses: statuses by severity without inconclusive, dropping those with no count anywhere", () => {
  const schema = realBundle.schema;
  const vs = realBundle.board.versions;
  const out = axisStatuses(vs, schema);
  const present = schema.statuses
    .filter(s => s.key !== "inconclusive")
    .filter(s => vs.some(v => Object.values(v.counts).some(c => (c[s.key] ?? 0) > 0)))
    .sort((a, b) => a.severity - b.severity)
    .map(s => s.key);
  expect(out).toEqual(present);
  expect(out).not.toContain("inconclusive");
});

test("clearDifferences keeps only improved/worse; null vs_baseline gives none", () => {
  const cur = realBundle.board.versions.find(v => v.name === realBundle.current)!;
  const expected = (cur.vs_baseline ?? []).filter(v => v.result === "improved" || v.result === "worse");
  expect(clearDifferences(cur)).toEqual(expected);
  const base: BoardVersion = { ...cur, vs_baseline: null, cohort: [] };
  expect(clearDifferences(base)).toEqual([]);
});

test("resultStatus maps gain results to status keys through tones", () => {
  const schema: Schema = stressBundle.schema;
  expect(resultStatus("improved", schema)).toBe(schema.statuses.find(s => s.tone === "good")!.key);
  expect(resultStatus("worse", schema)).toBe(schema.statuses.find(s => s.tone === "bad")!.key);
  expect(resultStatus("same", schema)).toBe(schema.statuses.find(s => s.tone === "neutral")!.key);
  expect(resultStatus("small", schema)).toBe(schema.statuses.find(s => s.tone === "neutral")!.key);
});

test("scoreText prints value [lo, hi] and n/a for missing parts", () => {
  expect(scoreText([1.234, 0.5, 2], 2)).toBe("1.23 [0.50, 2.00]");
  expect(scoreText([1.234, null, 2], 1)).toBe("1.2");
  expect(scoreText(null, 2)).toBe("n/a");
  expect(scoreText([null, 1, 2], 2)).toBe("n/a");
});
