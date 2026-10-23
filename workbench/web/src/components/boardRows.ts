import type { Generator, VsBaseline } from "../api";

// Melhor aprovação de textura entre as versões candidatas (a referência fica de fora).
// Empate: fica a primeira na ordem recebida; sem candidatas, null.
export function bestTexture(generators: Generator[]): { name: string; approved: number } | null {
  let best: { name: string; approved: number } | null = null;
  for (const gen of generators) {
    if (gen.is_baseline) continue;
    const approved = gen.counts.texture.approved;
    if (best === null || approved > best.approved) best = { name: gen.name, approved };
  }
  return best;
}

// Número com sinal para as fórmulas: "+6", "-6", "0"; null vira "–".
function signed(x: number | null): string {
  if (x === null || !Number.isFinite(x)) return "–";
  const rounded = Math.round(x * 100) / 100;
  return rounded > 0 ? `+${rounded}` : `${rounded}`;
}

// Fórmula da contagem de aprovados contra a referência: "8 → 14 = +6 · CI [+3, +9]".
export function formulaFor(vs: VsBaseline, before: number, after: number): string {
  const [lo, hi] = vs.ci;
  return `${before} → ${after} = ${signed(after - before)} · CI [${signed(lo)}, ${signed(hi)}]`;
}

// Ganho e intervalo de um indicador: "+6 [+3, +9]".
export function gainText(vs: VsBaseline): string {
  const [lo, hi] = vs.ci;
  return `${signed(vs.gain)} [${signed(lo)}, ${signed(hi)}]`;
}

// Indicador de aprovação de textura, quando o placar o oferece (hoje ele não vem no board).
export function approvedIndicator(indicators: VsBaseline[]): VsBaseline | undefined {
  return indicators.find(i => i.indicator === "approved" && i.group === "texture");
}

// Mediana mostrada na coluna "Median |Δ|": a métrica escolhida na ordenação se for métrica;
// senão a primeira de textura (GLCM, Wavelet ou NEx); senão a primeira disponível.
export function textureMetricKey(keys: string[], sortKey: string): string | null {
  if (keys.includes(sortKey)) return sortKey;
  const texture = keys.find(k => /^(glcm_|wavelet_|nex)/.test(k));
  return texture ?? keys[0] ?? null;
}
