import * as Observable from "@observablehq/plot";
import type { PlotOptions } from "./Plot";
import { BAND_FILL, GRID, TEXT_INK } from "../palette";
import type { SpectrumBand } from "../tools/series";
import { spreadValues } from "./labelSpread";

type Marks = NonNullable<PlotOptions["marks"]>;

// Margens fixas do gráfico de espectro: o afastamento dos rótulos depende da altura da área de dados.
export const SPECTRUM_MARGINS = { marginTop: 20, marginBottom: 30 } as const;
const LABEL_GAP_PX = 14;

// Domínio log-y em potências de dez, cobrindo a faixa e o topo. Quem chama usa o mesmo domínio no eixo.
export function spectrumYDomain(band: SpectrumBand[], lines: { power: number }[], top: number): [number, number] {
  const lows = [...band.map(b => b.lo), ...lines.map(l => l.power)].filter(v => v > 0);
  if (lows.length === 0) return [1, 10];
  const lo = 10 ** Math.floor(Math.log10(Math.min(...lows)));
  const hi = Math.max(10 ** Math.ceil(Math.log10(Math.max(top, lo))), lo * 10);
  return [lo, hi];
}

interface Options {
  band: SpectrumBand[];
  nyquist: number;
  // Topo usado para posicionar o rótulo "Nyquist".
  top: number;
  // `key` é o canal de cor (rótulo já resolvido em labelOf); `z` identifica a linha (uma por entidade).
  lines: { f: number; power: number; key: string; z: string }[];
  // Rótulo direto na ponta de cada linha (só com até 4 séries).
  direct: boolean;
  labelOf: (key: string) => string;
  // domínio log-y do eixo (spectrumYDomain) e altura total do gráfico, para afastar os rótulos
  yDomain: [number, number];
  height: number;
}

// Marcas comuns aos espectros: faixa P5–P95 (anotação, sem tooltip), Nyquist, linhas e rótulos diretos.
// O tooltip mostra f e potência com o nome da série, nunca o canal cru nem case_id.
// Os eixos e a escala de cor ficam a cargo do gráfico que chama.
export function spectrumMarks({ band, nyquist, top, lines, direct, labelOf, yDomain, height }: Options): Marks {
  // rótulos das pontas: afastados em px na escala log, sem mexer nos pontos
  const last = direct ? lastPerLine(lines) : [];
  const plotHeight = height - SPECTRUM_MARGINS.marginTop - SPECTRUM_MARGINS.marginBottom;
  const [lo, hi] = yDomain;
  const span = Math.log10(hi) - Math.log10(lo);
  const toPx = (v: number) => ((Math.log10(hi) - Math.log10(v)) / span) * plotHeight;
  const fromPx = (p: number) => 10 ** (Math.log10(hi) - (p / plotHeight) * span);
  const labelYs = spreadValues(last.map(p => p.power), toPx, fromPx, LABEL_GAP_PX);
  const ends = last.map((p, i) => ({ ...p, label: labelOf(p.key), labelY: labelYs[i] }));
  return [
    Observable.areaY(band, { x: "f", y1: "lo", y2: "hi", fill: BAND_FILL }),
    Observable.gridY({ stroke: GRID }),
    Observable.ruleX([nyquist], { stroke: "#8a8f8c" }),
    Observable.text([{ f: nyquist, p: top, label: "Nyquist" }], {
      x: "f",
      y: "p",
      text: "label",
      fill: TEXT_INK,
      textAnchor: "end",
      dx: -4,
      dy: 10,
    }),
    Observable.line(lines, {
      x: "f",
      y: "power",
      stroke: "key",
      z: "z",
      strokeWidth: 2,
      tip: { format: { stroke: labelOf, z: false } },
    }),
    ...(direct
      ? [
          Observable.dot(ends, {
            x: "f",
            y: "power",
            fill: "key",
            r: 4,
            stroke: "#fcfcfb",
            strokeWidth: 2,
            tip: { format: { fill: labelOf, z: false } },
          }),
          Observable.text(ends, {
            x: "f",
            y: "labelY",
            text: "label",
            fill: TEXT_INK,
            textAnchor: "start",
            dx: 8,
          }),
        ]
      : []),
  ];
}

// Último ponto (maior frequência) de cada linha.
function lastPerLine<T extends { f: number; z: string }>(points: T[]): T[] {
  const last = new Map<string, T>();
  for (const p of points) {
    const current = last.get(p.z);
    if (!current || p.f >= current.f) last.set(p.z, p);
  }
  return [...last.values()];
}
