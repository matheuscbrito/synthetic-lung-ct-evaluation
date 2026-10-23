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
  // `key` é o canal de cor (rótulo já resolvido em labelOf); `z` identifica a linha (uma por entidade).
  lines: { f: number; power: number; key: string; z: string }[];
  // Rótulo direto na ponta de cada linha (só com até 4 séries).
  direct: boolean;
  labelOf: (key: string) => string;
}

// Marcas comuns aos espectros: faixa P5–P95 (anotação, sem tooltip), Nyquist, linhas e rótulos diretos.
// O tooltip mostra f e potência com o nome da série, nunca o canal cru nem case_id.
// Os eixos e a escala de cor ficam a cargo do gráfico que chama.
export function spectrumMarks({ band, nyquist, top, lines, direct, labelOf }: Options): Marks {
  const ends = direct ? lastPerLine(lines).map(p => ({ ...p, label: labelOf(p.key) })) : [];
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

// Último ponto (maior frequência) de cada linha.
function lastPerLine<T extends { f: number; z: string }>(points: T[]): T[] {
  const last = new Map<string, T>();
  for (const p of points) {
    const current = last.get(p.z);
    if (!current || p.f >= current.f) last.set(p.z, p);
  }
  return [...last.values()];
}
