import { describe, expect, test } from "vitest";
import type { Generator } from "./api";
import { sortGenerators } from "./board";

function gen(name: string, patch: Partial<Generator> = {}): Generator {
  return {
    name,
    mode: "x",
    is_baseline: false,
    counts: {
      brightness: { approved: 0, review: 0, rejected: 0 },
      texture: { approved: 0, review: 0, rejected: 0 },
    },
    median_abs_z: {},
    vs_baseline: null,
    ...patch,
  };
}

const board: Generator[] = [
  gen("Zeta", { median_abs_z: { delta_mu: 0.5 } }),
  gen("Dsr", { is_baseline: true, median_abs_z: { delta_mu: 1 } }),
  gen("Alpha", { median_abs_z: { delta_mu: 2 } }),
  gen("Mid", { median_abs_z: { delta_mu: null } }),
];

describe("sortGenerators", () => {
  test("baseline stays first for every key", () => {
    for (const key of ["history", "name", "brightness", "texture", "delta_mu", "missing"]) {
      const sorted = sortGenerators(board, key);
      expect(sorted[0].is_baseline, key).toBe(true);
      expect(sorted.map(g => g.name).sort()).toEqual(board.map(g => g.name).sort());
    }
  });

  test("history keeps the received order after the baseline", () => {
    expect(sortGenerators(board, "history").map(g => g.name)).toEqual(["Dsr", "Zeta", "Alpha", "Mid"]);
  });

  test("name sorts the non-baseline rows alphabetically", () => {
    expect(sortGenerators(board, "name").map(g => g.name)).toEqual(["Dsr", "Alpha", "Mid", "Zeta"]);
  });

  test("metric key sorts by descending median |z|, null last", () => {
    expect(sortGenerators(board, "delta_mu").map(g => g.name)).toEqual(["Dsr", "Alpha", "Zeta", "Mid"]);
  });

  test("texture sorts by rejected count, most rejected first", () => {
    const counted = [
      gen("A", { counts: { brightness: { approved: 0, review: 0, rejected: 0 }, texture: { approved: 0, review: 0, rejected: 1 } } }),
      gen("B", { counts: { brightness: { approved: 0, review: 0, rejected: 0 }, texture: { approved: 0, review: 0, rejected: 5 } } }),
      gen("Dsr", { is_baseline: true }),
    ];
    expect(sortGenerators(counted, "texture").map(g => g.name)).toEqual(["Dsr", "B", "A"]);
  });

  test("does not mutate the input", () => {
    const before = board.map(g => g.name);
    sortGenerators(board, "name");
    expect(board.map(g => g.name)).toEqual(before);
  });
});
