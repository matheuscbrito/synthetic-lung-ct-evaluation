import { describe, expect, test } from "vitest";
import type { Run } from "../contract/types";
import { realBundle, stressBundle } from "../fixtures";
import { OTHER, SERIES } from "../palette";
import { paramText, rankRuns, reachX, runScore, stepColumns } from "./runs";

const real = realBundle.runs!;
const stress = stressBundle.runs!;

describe("rankRuns", () => {
  test("real: GP-BO ranks first and reaches its best at budget 119", () => {
    const ranked = rankRuns(real.runs);
    expect(ranked[0].key).toBe("gp");
    expect(ranked[0].toBest).toBe(119);
  });

  test("sorted by best, descending; ties keep the original order", () => {
    const ranked = rankRuns(real.runs);
    const bests = ranked.map(r => r.best);
    expect(bests).toEqual([...bests].sort((a, b) => (b ?? 0) - (a ?? 0)));
    expect(ranked.map(r => r.key)).toEqual(
      [...real.runs].sort((a, b) => (b.summary.best ?? 0) - (a.summary.best ?? 0)).map(r => r.key),
    );
  });

  test("colour follows the original index, not the rank", () => {
    const ranked = rankRuns(real.runs);
    expect(ranked.find(r => r.key === "gp")!.color).toBe(SERIES[0]);
    expect(ranked.find(r => r.key === "nm")!.color).toBe(SERIES[1]);
  });

  test("carries summary fields and the derived reach", () => {
    const gp = real.runs.find(r => r.key === "gp")!;
    const row = rankRuns(real.runs).find(r => r.key === "gp")!;
    expect(row).toMatchObject({
      key: "gp",
      label: gp.label,
      best: gp.summary.best,
      evaluated: gp.summary.evaluated,
      used: gp.summary.used,
    });
    expect(row.toBest).toBe(reachX(gp));
  });

  test("a run without a best is listed last with no reach", () => {
    const nobest: Run = { ...real.runs[0], key: "x", summary: { ...real.runs[0].summary, best: null } };
    const ranked = rankRuns([nobest, ...real.runs]);
    expect(ranked[ranked.length - 1].key).toBe("x");
    expect(ranked[ranked.length - 1].toBest).toBeNull();
    expect(ranked[ranked.length - 1].best).toBeNull();
  });
});

describe("reachX", () => {
  test("first budget whose score reaches the best; null when the curve never does", () => {
    const gp = real.runs.find(r => r.key === "gp")!;
    expect(reachX(gp)).toBe(119);
    expect(reachX({ ...gp, summary: { ...gp.summary, best: 1e9 } })).toBeNull();
  });
});

describe("stepColumns", () => {
  test("real: stage and W/L columns exist, params listed in the order of the union", () => {
    const gp = real.runs.find(r => r.key === "gp")!;
    const cols = stepColumns(gp, real.params);
    expect(cols.stage).toBe(true);
    expect(cols.wl).toBe(true);
    expect(cols.params.map(p => p.key)).toEqual(real.params.map(p => p.key).filter(k => gp.steps.some(s => k in s.params)));
  });

  test("stress: no Stage and no W/L columns", () => {
    const cols = stepColumns(stress.runs[0], stress.params);
    expect(cols.stage).toBe(false);
    expect(cols.wl).toBe(false);
    expect(cols.params.map(p => p.key)).toEqual(stress.params.map(p => p.key));
  });

  test("a parameter that no step carries is not a column", () => {
    const gp = real.runs.find(r => r.key === "gp")!;
    const extra = [...real.params, { key: "ghost", label: "ghost" }];
    expect(stepColumns(gp, extra).params.map(p => p.key)).not.toContain("ghost");
  });
});

describe("text helpers", () => {
  test("paramText prints numbers like :g, keeps strings, dashes missing values", () => {
    expect(paramText(0.767)).toBe("0.767");
    expect(paramText(2)).toBe("2");
    expect(paramText("ddim")).toBe("ddim");
    expect(paramText(null)).toBe("–");
    expect(paramText(true)).toBe("true");
  });

  test("runScore: signed with one decimal and the unit; n/a for null", () => {
    expect(runScore(44.1667, "%")).toBe("+44.2%");
    expect(runScore(-60.7, "pts")).toBe("−60.7 pts");
    expect(runScore(null, "%")).toBe("n/a");
  });

  test("the fallback colour is never a series colour", () => {
    expect(SERIES).not.toContain(OTHER);
  });
});
