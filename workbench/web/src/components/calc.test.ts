import { describe, expect, test } from "vitest";
import { calcLines } from "./calc";
import type { Metric } from "../api";

function metric(over: Partial<Metric>): Metric {
  return {
    key: "glcm_contrast",
    label: "GLCM contrast",
    group: "texture",
    technique: "GLCM",
    real: 5.232,
    synthetic: 2.434,
    value: -1.72,
    z: -1.72,
    status: "review",
    unit: "IQR",
    ...over,
  };
}

describe("calcLines", () => {
  test("z metric: formula Δ ÷ IQR, signed result and review/rejected rule", () => {
    expect(calcLines(metric({}))).toEqual({
      formula: "Δ ÷ IQR",
      result: "= -1.72",
      rule: "review > 1 · rejected > 2",
    });
  });

  test("z metric: non-negative z gets an explicit plus sign", () => {
    expect(calcLines(metric({ z: 0.4, value: 0.4, status: "approved" })).result).toBe("= +0.40");
  });

  test("sat31: value in percent and the 15% limit, no formula", () => {
    expect(calcLines(metric({ key: "sat31", label: "GLCM Sat31", group: "brightness", z: null, value: 0.8, unit: "%", real: null, synthetic: null, status: "approved" }))).toEqual({
      formula: null,
      result: "0.8%",
      rule: "limit 15%",
    });
  });

  test("nex: no formula or result, real P5–P95 band as rule", () => {
    expect(calcLines(metric({ key: "nex", label: "NEx", group: "texture", technique: "NEx", z: null, value: -0.063, unit: "NEx" }))).toEqual({
      formula: null,
      result: null,
      rule: "real P5–P95 band",
    });
  });
});
