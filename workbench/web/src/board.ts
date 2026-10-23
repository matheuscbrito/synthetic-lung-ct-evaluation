import type { Generator, ResultLabel } from "./api";

// Cor do chip de resultado por indicador (mudança contra a referência).
export const RESULT_COLOR: Record<ResultLabel, string> = {
  improved: "#2f9e57",
  worse: "#c0392b",
  "small change": "#8a8f8c",
  "no clear difference": "#b8bdbb",
  "n/a": "#d0d0d0",
};

// Chaves de ordenação: "history" (ordem recebida), "name", "brightness" / "texture"
// (mais reprovados primeiro) ou uma métrica de median_abs_z (maior |z| primeiro, null no fim).
export type GeneratorSortKey = "history" | "name" | "brightness" | "texture" | string;

function compareIds(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

function score(gen: Generator, key: GeneratorSortKey): number {
  if (key === "brightness" || key === "texture") return gen.counts[key].rejected;
  const z = gen.median_abs_z[key];
  return z === null || z === undefined ? -Infinity : z;
}

// A referência fica sempre na primeira linha, qualquer que seja a chave.
export function sortGenerators(gens: Generator[], key: GeneratorSortKey): Generator[] {
  const out = [...gens];
  if (key === "name") {
    out.sort((a, b) => compareIds(a.name, b.name));
  } else if (key !== "history") {
    out.sort((a, b) => score(b, key) - score(a, key) || compareIds(a.name, b.name));
  }
  // sort é estável: a referência vai à frente mantendo a ordem relativa dos demais
  return out.sort((a, b) => Number(b.is_baseline) - Number(a.is_baseline));
}
