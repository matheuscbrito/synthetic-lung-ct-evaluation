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

// Linha da contagem de aprovados de textura contra a referência: "Texture approved 8 → 14 = +6".
export function approvedLine(before: number, after: number): string {
  return `Texture approved ${before} → ${after} = ${signed(after - before)}`;
}

// Ganho e intervalo de um indicador: "+6 [+3, +9]".
export function gainText(vs: VsBaseline): string {
  const [lo, hi] = vs.ci;
  return `${signed(vs.gain)} [${signed(lo)}, ${signed(hi)}]`;
}

// Mediana mostrada na coluna "Median |Δ|": a métrica escolhida na ordenação se for métrica;
// senão a primeira de textura (GLCM, Wavelet ou NEx); senão a primeira disponível.
export function textureMetricKey(keys: string[], sortKey: string): string | null {
  if (keys.includes(sortKey)) return sortKey;
  const texture = keys.find(k => /^(glcm_|wavelet_|nex)/.test(k));
  return texture ?? keys[0] ?? null;
}
