import type { Slice, Status, Verdict } from "../api";
import { sortSlices } from "../status";

export interface DatasetSummary {
  counts: Record<"approved" | "review" | "rejected", number>;
  bars: { caseId: string; worst: number; status: Status }[];
  outOfRange: Record<string, number>;
}

// |z| máximo entre as métricas do veredito com z; sem métrica com z, vale 0.
function worstOf(slice: Slice, verdict: Verdict): number {
  let worst = 0;
  for (const metric of slice.metrics) {
    if (metric.group === verdict && metric.z !== null) worst = Math.max(worst, Math.abs(metric.z));
  }
  return worst;
}

// Resumo do dataset para o cartão de KPIs: contagens, barras na ordem do pior e fora de faixa por técnica.
export function datasetSummary(slices: Slice[], verdict: Verdict): DatasetSummary {
  const counts = { approved: 0, review: 0, rejected: 0 };
  const outOfRange: Record<string, number> = {};

  for (const slice of slices) {
    const block = slice[verdict];
    if (block.verdict in counts) counts[block.verdict as keyof typeof counts] += 1;
    for (const technique of Object.keys(block.techniques)) {
      outOfRange[technique] ??= 0;
      if (block.techniques[technique] !== "approved") outOfRange[technique] += 1;
    }
  }

  const bars = sortSlices(slices, verdict, "worst").map(slice => ({
    caseId: slice.case_id,
    worst: worstOf(slice, verdict),
    status: slice[verdict].verdict,
  }));

  return { counts, bars, outOfRange };
}

// Busca por substring do rótulo, sem diferenciar maiúsculas; consulta vazia mantém tudo.
export function searchSlices(slices: Slice[], query: string): Slice[] {
  const needle = query.trim().toLowerCase();
  if (needle === "") return slices;
  return slices.filter(slice => slice.label.toLowerCase().includes(needle));
}
