import { describe, expect, test } from "vitest";
import { datasetSummary, searchSlices } from "./datasetSummary";
import type { Metric, Slice, Status } from "../api";

function metric(key: string, group: "texture" | "brightness", z: number | null, status: Status): Metric {
  return {
    key, label: key, group, technique: "GLCM", real: 0, synthetic: 0, value: z, z, status, unit: "IQR",
  };
}

function mk(
  caseId: string,
  label: string,
  patient: string,
  texture: Status,
  techniques: Record<string, Status>,
  metrics: Metric[],
): Slice {
  return {
    case_id: caseId,
    label,
    patient,
    pair_mode: "x",
    mask_only: false,
    brightness: { verdict: "approved", techniques: {} },
    texture: { verdict: texture, techniques },
    metrics,
    density: { status: "ok", median_shift_iqr: 0 },
    wavelet_type: "textura preservada",
  };
}

// A: review, pior |z| 2.5 · B: approved, pior |z| 0.5 · C: rejected, pior |z| 4 (brilho com z 9 não conta)
const fixture: Slice[] = [
  mk("A", "P100 · 058", "100", "review", { GLCM: "review", Wavelet: "approved", NEx: "rejected" }, [
    metric("k1", "texture", 2.5, "review"),
    metric("k2", "texture", -1, "approved"),
  ]),
  mk("B", "P100 · 059", "100", "approved", { GLCM: "approved", Wavelet: "review", NEx: "approved" }, [
    metric("k1", "texture", 0.5, "approved"),
  ]),
  mk("C", "P105 · 078", "105", "rejected", { GLCM: "rejected", Wavelet: "approved", NEx: "approved" }, [
    metric("k1", "texture", -4, "rejected"),
    metric("k3", "texture", null, "approved"),
    metric("b1", "brightness", 9, "rejected"),
  ]),
];

describe("datasetSummary", () => {
  test("counts slices by verdict of the group", () => {
    const { counts } = datasetSummary(fixture, "texture");
    expect(counts).toEqual({ approved: 1, review: 1, rejected: 1 });
  });

  test("bars follow worst order with worst |z| and status", () => {
    const { bars } = datasetSummary(fixture, "texture");
    expect(bars.map(b => b.caseId)).toEqual(["C", "A", "B"]);
    expect(bars.map(b => b.worst)).toEqual([4, 2.5, 0.5]);
    expect(bars.map(b => b.status)).toEqual(["rejected", "review", "approved"]);
  });

  test("outOfRange counts slices whose technique is not approved", () => {
    const { outOfRange } = datasetSummary(fixture, "texture");
    expect(outOfRange).toEqual({ GLCM: 2, Wavelet: 1, NEx: 1 });
  });

  test("technique with no problems counts zero", () => {
    const slices = [mk("X", "P1 · 001", "1", "approved", { GLCM: "approved" }, [])];
    expect(datasetSummary(slices, "texture").outOfRange).toEqual({ GLCM: 0 });
  });

  test("empty dataset gives empty summary", () => {
    expect(datasetSummary([], "texture")).toEqual({
      counts: { approved: 0, review: 0, rejected: 0 },
      bars: [],
      outOfRange: {},
    });
  });
});

describe("searchSlices", () => {
  test("empty query keeps every slice", () => {
    expect(searchSlices(fixture, "  ").map(s => s.case_id)).toEqual(["A", "B", "C"]);
  });

  test("matches label substring ignoring case", () => {
    expect(searchSlices(fixture, "p100").map(s => s.case_id)).toEqual(["A", "B"]);
    expect(searchSlices(fixture, "105").map(s => s.case_id)).toEqual(["C"]);
    expect(searchSlices(fixture, "999")).toEqual([]);
  });
});
