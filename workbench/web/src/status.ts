import type { Slice, Status, Verdict } from "./api";

export const COLOR: Record<Status, string> = {
  approved: "#2f9e57",
  review: "#d9a21b",
  rejected: "#c0392b",
  inconclusive: "#b8bdbb",
};

export const SEVERITY: Record<Status, number> = {
  rejected: 3,
  review: 2,
  inconclusive: 1,
  approved: 0,
};

export type SortKey = "worst" | "name" | string;

// |z| máximo entre as métricas do veredito; métrica sem z conta como 0.
function maxAbsZ(slice: Slice, verdict: Verdict): number {
  let max = 0;
  for (const metric of slice.metrics) {
    if (metric.group === verdict && metric.z !== null) max = Math.max(max, Math.abs(metric.z));
  }
  return max;
}

function metricAbsZ(slice: Slice, key: string): number {
  const metric = slice.metrics.find(m => m.key === key);
  if (!metric || metric.z === null) return -Infinity;
  return Math.abs(metric.z);
}

export function sortSlices(slices: Slice[], verdict: Verdict, by: SortKey): Slice[] {
  const out = [...slices];
  if (by === "worst") {
    return out.sort((a, b) =>
      SEVERITY[b[verdict].verdict] - SEVERITY[a[verdict].verdict] ||
      maxAbsZ(b, verdict) - maxAbsZ(a, verdict) ||
      compareIds(a.case_id, b.case_id));
  }
  if (by === "name") {
    return out.sort((a, b) => compareIds(a.case_id, b.case_id));
  }
  return out.sort((a, b) => metricAbsZ(b, by) - metricAbsZ(a, by) || compareIds(a.case_id, b.case_id));
}

function compareIds(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

// Vizinho na lista, parado nas pontas (não dá a volta).
export function neighbour(ids: string[], current: string, step: -1 | 1): string {
  const index = ids.indexOf(current);
  if (index < 0 || ids.length === 0) return current;
  const next = Math.min(Math.max(index + step, 0), ids.length - 1);
  return ids[next];
}
