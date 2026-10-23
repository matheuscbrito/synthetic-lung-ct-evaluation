import { useMemo } from "react";
import * as Observable from "@observablehq/plot";
import type { Nex } from "../api";
import { Info } from "../components/Info";
import { Plot, type PlotOptions } from "../components/Plot";
import { num } from "../format";
import { BAND_FILL, REFERENCE_INK, SEQUENTIAL, SERIES } from "../palette";
import { useToolData } from "./toolData";

const REAL = REFERENCE_INK;
const SYNTHETIC = SERIES[0];
const WIDTH = 640;
const WINDOW_WIDTH = 300;

interface Props {
  version: string;
  caseId: string;
}

interface Rect {
  x1: number;
  x2: number;
  y1: number;
  y2: number;
  v: number;
  t: string;
}

function finite(x: number | null | undefined): x is number {
  return typeof x === "number" && Number.isFinite(x);
}

// Janelas com valor: cada janela é um retângulo de lado `tile` em (col, row).
// O tooltip traz o valor primeiro, depois a posição da janela.
function rectsOf(windows: Nex["real"], tile: number): Rect[] {
  const out: Rect[] = [];
  for (const w of windows) {
    if (finite(w.value)) {
      out.push({
        x1: w.col,
        x2: w.col + tile,
        y1: w.row,
        y2: w.row + tile,
        v: w.value,
        t: `${num(w.value, 3)} · col ${w.col}, row ${w.row}`,
      });
    }
  }
  return out;
}

function windowMap(title: string, rects: Rect[], extent: [number, number], width: number, height: number): PlotOptions {
  return {
    width: WINDOW_WIDTH,
    height: Math.round((WINDOW_WIDTH * height) / Math.max(width, 1)),
    title,
    x: { domain: [0, width], axis: null, padding: 0 },
    y: { domain: [0, height], axis: null, reverse: true, padding: 0 },
    color: {
      type: "linear",
      domain: extent,
      range: [SEQUENTIAL[0], SEQUENTIAL[6]],
      legend: true,
    },
    marks: [
      Observable.rect(rects, { x1: "x1", x2: "x2", y1: "y1", y2: "y2", fill: "v", title: "t", tip: true }),
    ],
  };
}

export function NexTool({ version, caseId }: Props) {
  const { data, error } = useToolData<Nex>("nex", version, caseId);

  const plots = useMemo(() => {
    if (!data) return null;
    const real = rectsOf(data.real, data.tile);
    const synthetic = rectsOf(data.synthetic, data.tile);
    const all = [...real, ...synthetic].map(r => r.v);
    const lo = all.length ? Math.min(...all) : 0;
    const hi = all.length ? Math.max(...all) : 1;
    const extent: [number, number] = hi > lo ? [lo, hi] : [lo, lo + 1];

    // Largura e altura do mapa de janelas: extensão máxima das janelas (todas, inclusive as nulas).
    const ends = [...data.real, ...data.synthetic];
    const width = Math.max(data.tile, ...ends.map(w => w.col + data.tile));
    const height = Math.max(data.tile, ...ends.map(w => w.row + data.tile));

    const points = [
      ...(finite(data.value_real) ? [{ v: data.value_real, which: "real" }] : []),
      ...(finite(data.value_synthetic) ? [{ v: data.value_synthetic, which: "synthetic" }] : []),
    ];
    const band = finite(data.p5) && finite(data.p95) ? [{ x1: data.p5, x2: data.p95 }] : [];

    const axis: PlotOptions = {
      width: WIDTH,
      height: 120,
      marginLeft: 80,
      x: { label: null },
      y: { domain: ["real", "synthetic"], label: null },
      color: { domain: ["real", "synthetic"], range: [REAL, SYNTHETIC] },
      marks: [
        Observable.rectX(band, { x1: "x1", x2: "x2", fill: BAND_FILL, tip: true }),
        // Anel da cor de superfície separa o ponto da faixa e de outro ponto próximo.
        Observable.dot(points, {
          x: "v",
          y: "which",
          fill: "which",
          r: 6,
          stroke: "#fcfcfb",
          strokeWidth: 2,
          title: "which",
          tip: true,
        }),
      ],
    };

    return {
      axis,
      real: windowMap("Real", real, extent, width, height),
      synthetic: windowMap("Synthetic", synthetic, extent, width, height),
    };
  }, [data]);

  return (
    <div className="tool">
      <h3 className="tool-title">
        NEx <Info term="nex" />
      </h3>
      {error && <p className="tool-error">{error}</p>}
      {data && plots && (
        <>
          <Plot options={plots.axis} />
          <dl className="tool-figures">
            <dt>Real</dt>
            <dd>{num(data.value_real)}</dd>
            <dt>Synthetic</dt>
            <dd>{num(data.value_synthetic)}</dd>
            <dt>P5</dt>
            <dd>{num(data.p5)}</dd>
            <dt>P95</dt>
            <dd>{num(data.p95)}</dd>
          </dl>
          <div className="tool-row">
            <Plot options={plots.real} />
            <Plot options={plots.synthetic} />
          </div>
        </>
      )}
    </div>
  );
}
