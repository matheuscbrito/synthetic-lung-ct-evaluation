import * as Observable from "@observablehq/plot";
import type { PlotOptions } from "./Plot";
import { BAND_FILL, GRID, TEXT_INK } from "../palette";
import type { SpectrumBand } from "../tools/series";

type Marks = NonNullable<PlotOptions["marks"]>;

interface Options {
  band: SpectrumBand[];
  nyquist: number;
  // Topo usado para posicionar o rótulo "Nyquist".
  top: number;
  // `key` é o canal de cor: "real", "synthetic" ou o nome da versão/corte.
  lines: { f: number; power: number; key: string }[];
  // Rótulo direto na ponta de cada linha (só com até 4 séries).
  direct: boolean;
  labelOf: (key: string) => string;
}

// Marcas comuns aos espectros: faixa P5–P95, Nyquist, linhas e rótulos diretos na ponta.
// Os eixos e a escala de cor ficam a cargo do gráfico que chama.
export function spectrumMarks({ band, nyquist, top, lines, direct, labelOf }: Options): Marks {
  const ends = direct
    ? lastPerKey(lines).map(p => ({ ...p, label: labelOf(p.key) }))
    : [];
  return [
    Observable.areaY(band, { x: "f", y1: "lo", y2: "hi", fill: BAND_FILL, tip: false }),
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
    Observable.line(lines, { x: "f", y: "power", stroke: "key", z: "key", strokeWidth: 2, tip: true }),
    ...(direct
      ? [
          Observable.dot(ends, { x: "f", y: "power", fill: "key", r: 4, stroke: "#fcfcfb", strokeWidth: 2, tip: true }),
          Observable.text(ends, {
            x: "f",
            y: "power",
            text: "label",
            fill: TEXT_INK,
            textAnchor: "start",
            dx: 8,
          }),
        ]
      : []),
  ];
}

// Último ponto (maior frequência) de cada série.
function lastPerKey<T extends { f: number; key: string }>(points: T[]): T[] {
  const last = new Map<string, T>();
  for (const p of points) {
    const current = last.get(p.key);
    if (!current || p.f >= current.f) last.set(p.key, p);
  }
  return [...last.values()];
}
