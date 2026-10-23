import { useMemo } from "react";
import * as Observable from "@observablehq/plot";
import type { Glcm } from "../api";
import { Info } from "../components/Info";
import { Plot, type PlotOptions } from "../components/Plot";
import { divergingScale, sequentialScale } from "../palette";
import { num } from "../format";
import { useToolData } from "./toolData";
import { glcmDiff } from "./series";

const SIZE = 200;

interface Cell {
  x: number;
  y: number;
  v: number;
}

interface Props {
  version: string;
  caseId: string;
}

// Células finitas da matriz; null/NaN ficam de fora.
function cellsOf(matrix: number[][]): Cell[] {
  const out: Cell[] = [];
  matrix.forEach((row, i) =>
    row.forEach((v, j) => {
      if (Number.isFinite(v)) out.push({ x: j, y: i, v });
    }),
  );
  return out;
}

function maxAbs(values: Cell[]): number {
  return Math.max(1e-12, ...values.map(c => Math.abs(c.v)));
}

function pct(x: number | null): string {
  return x === null || !Number.isFinite(x) ? "–" : `${num(x, 1)}%`;
}

// Domínios são listas de índices: com [0, levels] a escala de banda do Plot trata como duas categorias.
// O tooltip mostra o valor primeiro, depois a posição (tom de linha e coluna).
export function heatmap(title: string, cells: Cell[], levels: number, color: PlotOptions["color"]): PlotOptions {
  const indices = Array.from({ length: levels }, (_, i) => i);
  const rows = cells.map(c => ({ ...c, t: `${num(c.v, 4)} · row ${c.y}, col ${c.x}` }));
  return {
    width: SIZE,
    height: SIZE,
    title,
    x: { domain: indices, axis: null, padding: 0 },
    y: { domain: indices, axis: null, reverse: true, padding: 0 },
    color,
    marks: [Observable.cell(rows, { x: "x", y: "y", fill: "v", title: "t", tip: true })],
  };
}

export function GlcmTool({ version, caseId }: Props) {
  const { data, error } = useToolData<Glcm>("glcm", version, caseId);

  const plots = useMemo(() => {
    if (!data) return null;
    const real = cellsOf(data.real);
    const synthetic = cellsOf(data.synthetic);
    const diff = cellsOf(glcmDiff(data));
    const top = Math.max(1e-12, ...real.map(c => c.v), ...synthetic.map(c => c.v));
    const range = maxAbs(diff);
    // Matrizes de coocorrência são sequenciais e não negativas: um tom só, do claro ao escuro.
    // Real e sintético dividem o mesmo domínio; a legenda sequencial aparece uma vez (no real).
    const shared = sequentialScale(0, top);
    return {
      real: heatmap("Real", real, data.levels, { ...shared, legend: true }),
      synthetic: heatmap("Synthetic", synthetic, data.levels, { ...shared, legend: false }),
      // Diferença tem sinal: divergente com meio neutro no zero e domínio simétrico.
      diff: heatmap("Synthetic − real", diff, data.levels, { ...divergingScale(range), legend: true }),
    };
  }, [data]);

  return (
    <div className="tool">
      <h3 className="tool-title">
        GLCM <Info term="glcm_contrast" />
      </h3>
      {error && <p className="tool-error">{error}</p>}
      {plots && (
        <>
          <div className="tool-row">
            <Plot options={plots.real} />
            <Plot options={plots.synthetic} />
            <Plot options={plots.diff} />
          </div>
          <dl className="tool-figures">
            <dt>Real tone 0</dt>
            <dd>{pct(data!.tones.real.zero_pct)}</dd>
            <dt>Real tone {data!.levels - 1}</dt>
            <dd>{pct(data!.tones.real.top_pct)}</dd>
            <dt>Synthetic tone 0</dt>
            <dd>{pct(data!.tones.synthetic.zero_pct)}</dd>
            <dt>Synthetic tone {data!.levels - 1}</dt>
            <dd>{pct(data!.tones.synthetic.top_pct)}</dd>
          </dl>
        </>
      )}
    </div>
  );
}
