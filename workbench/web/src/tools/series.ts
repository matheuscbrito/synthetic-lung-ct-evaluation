import type { Glcm, Spectrum } from "../api";

// Valor utilizável em gráfico: finito (null e NaN ficam de fora).
function finite(x: number | null | undefined): x is number {
  return typeof x === "number" && Number.isFinite(x);
}

// Escala log-y: potência e limites da faixa precisam ser estritamente positivos.
function positive(x: number | null | undefined): x is number {
  return finite(x) && x > 0;
}

export interface SpectrumBand {
  f: number;
  lo: number;
  hi: number;
}

export interface SpectrumLine {
  f: number;
  power: number;
  which: "real" | "synthetic";
}

// Pontos prontos para o Plot: linhas (real e sintético) e faixa P5–P95 de referência.
export function spectrumSeries(s: Spectrum): { band: SpectrumBand[]; lines: SpectrumLine[] } {
  const band: SpectrumBand[] = [];
  const lines: SpectrumLine[] = [];
  s.freq.forEach((f, i) => {
    const lo = s.ref_p5[i];
    const hi = s.ref_p95[i];
    if (positive(lo) && positive(hi)) band.push({ f, lo, hi });
    const real = s.real[i];
    const synthetic = s.synthetic[i];
    if (positive(real)) lines.push({ f, power: real, which: "real" });
    if (positive(synthetic)) lines.push({ f, power: synthetic, which: "synthetic" });
  });
  return { band, lines };
}

// Diferença sintético − real, célula a célula (mesma matriz 32×32 do GLCM).
export function glcmDiff(g: Glcm): number[][] {
  return g.real.map((row, i) => row.map((value, j) => g.synthetic[i][j] - value));
}
