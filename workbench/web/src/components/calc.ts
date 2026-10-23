import type { Metric } from "../api";

export interface CalcLines {
  formula: string | null;
  result: string | null;
  rule: string;
}

// Linhas de cálculo mostradas abaixo de uma métrica: z em IQR, sat31 em % e NEx pela faixa real.
export function calcLines(metric: Metric): CalcLines {
  if (metric.key === "sat31") {
    return {
      formula: null,
      result: metric.value === null || !Number.isFinite(metric.value) ? null : `${metric.value.toFixed(1)}%`,
      rule: "limit 15%",
    };
  }
  if (metric.key === "nex") {
    return { formula: null, result: null, rule: "real P5–P95 band" };
  }
  if (metric.z !== null && Number.isFinite(metric.z)) {
    const sign = metric.z >= 0 ? "+" : "";
    return {
      formula: "Δ ÷ IQR",
      result: `= ${sign}${metric.z.toFixed(2)}`,
      rule: "review > 1 · rejected > 2",
    };
  }
  return { formula: null, result: null, rule: "" };
}
