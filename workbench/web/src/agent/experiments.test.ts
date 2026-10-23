import { describe, expect, test } from "vitest";
import type { NotebookRow } from "../api";
import { gainLabel, lineage, signedPercent, trajectory, verdictTint } from "./experiments";

function row(id: string, base: string, vals: number[], search: string, best = false): NotebookRow {
  return {
    id,
    base,
    change: `mudança ${id}`,
    gain_text: vals.length ? vals.map(v => `+${v}%`).join(" / ") : "n/d",
    vals,
    scope: null,
    verdict: "melhor",
    reason: "",
    best,
    search,
  };
}

const ROWS: NotebookRow[] = [
  row("A1", "baseline", [5], "Matheus"),
  row("A2", "A1", [10, 8, 7], "Matheus"),
  row("A3", "A2", [], "Matheus"),
  row("A4", "A3", [12, 11, 9.5], "Matheus", true),
  row("B1", "baseline", [7.8], "Lucas"),
  row("B2", "B1", [20], "Lucas"),
  row("C1", "C2", [1], "Cyc"),
  row("C2", "C1", [2], "Cyc"),
  row("X1", "ghost", [3], "Orphan"),
  row("N1", "baseline", [], "Empty"),
];

describe("lineage", () => {
  test("goes from the root to the id, following base", () => {
    expect(lineage(ROWS, "A4")).toEqual(["A1", "A2", "A3", "A4"]);
    expect(lineage(ROWS, "B2")).toEqual(["B1", "B2"]);
  });

  test("a root row is its own lineage", () => {
    expect(lineage(ROWS, "A1")).toEqual(["A1"]);
  });

  test("stops at an unknown base id", () => {
    expect(lineage(ROWS, "X1")).toEqual(["X1"]);
  });

  test("a cycle terminates without repeating ids", () => {
    expect(lineage(ROWS, "C1")).toEqual(["C2", "C1"]);
  });

  test("unknown id gives an empty lineage", () => {
    expect(lineage(ROWS, "nope")).toEqual([]);
  });
});

describe("trajectory", () => {
  test("uses the best row of each search, keeping only rows with numbers", () => {
    const t = trajectory(ROWS);
    const matheus = t.find(s => s.search === "Matheus");
    expect(matheus).toEqual({ search: "Matheus", ids: ["A1", "A2", "A4"], values: [5, 7, 9.5] });
  });

  test("without a best row, anchors on the last row with numbers", () => {
    const lucas = trajectory(ROWS).find(s => s.search === "Lucas");
    expect(lucas).toEqual({ search: "Lucas", ids: ["B1", "B2"], values: [7.8, 20] });
  });

  test("searches without any numbers are left out", () => {
    expect(trajectory(ROWS).map(s => s.search)).not.toContain("Empty");
  });

  test("a cycle inside a search does not loop", () => {
    const cyc = trajectory(ROWS).find(s => s.search === "Cyc");
    expect(cyc?.ids).toEqual(["C1", "C2"]);
  });
});

describe("verdict tint and number", () => {
  test("verdicts map to the pill tints of the constraints", () => {
    expect(verdictTint("melhor")).toEqual(["#e7f4ec", "#1f7a43"]);
    expect(verdictTint("insuficiente")).toEqual(["#fbf1dc", "#9a6408"]);
    expect(verdictTint("pior")).toEqual(["#fbe6e3", "#a83224"]);
    expect(verdictTint("interrompida")).toEqual(["#eeeeec", "#6b6b66"]);
  });

  test("percent has one decimal and a sign", () => {
    expect(signedPercent(23.05)).toBe("+23.1%");
    expect(signedPercent(-1.04)).toBe("-1.0%");
    expect(signedPercent(0)).toBe("+0.0%");
  });
});

describe("gainLabel", () => {
  test("shows the last number with its sign", () => {
    expect(gainLabel({ ...row("A", "baseline", [7.3, 5.3, 4.8], "M"), scope: null })).toBe("+4.8%");
  });

  test("single-scope values show the scope as a suffix", () => {
    expect(gainLabel({ ...row("A", "baseline", [4.4], "M"), scope: "10" })).toBe("+4.4% · 10");
  });

  test("rows without numbers show the notebook text, truncated", () => {
    expect(gainLabel({ ...row("A", "baseline", [], "M"), gain_text: "n/d (7 casos)" })).toBe("n/d (7 casos)");
    const long = "nenhum número nesta linha, só uma explicação comprida do caderno";
    const label = gainLabel({ ...row("A", "baseline", [], "M"), gain_text: long });
    expect(label.endsWith("…")).toBe(true);
    expect(label.length).toBeLessThanOrEqual(28);
    expect(long.startsWith(label.slice(0, -1))).toBe(true);
  });

  test("never returns the bare n/d placeholder when the notebook has text", () => {
    expect(gainLabel({ ...row("A", "baseline", [], "M"), gain_text: "insuficiente: 2 cortes" })).not.toBe("n/d");
  });
});
