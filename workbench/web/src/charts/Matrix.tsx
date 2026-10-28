// Matrizes lado a lado (uma por painel) numa escala comum de um tom. Porta de render_v3.py (matrix_html).
import type { MatrixPayload } from "../contract/types";
import { SERIES } from "../palette";
import { isNum } from "./num";

interface Props {
  payload: MatrixPayload;
}

// mesmo azul do mockup (#2a78d6), com opacidade pela raiz do valor relativo ao máximo
const [R, G, B] = [1, 3, 5].map(i => parseInt(SERIES[0].slice(i, i + 2), 16));

export function Matrix({ payload: p }: Props) {
  const all = p.panels.flatMap(pn => pn.values.flat()).filter(isNum);
  const vmax = Math.max(0, ...all) || 1;
  const nCols = Math.max(1, p.cols.length);
  return (
    <div className="chart-matrix">
      <div className="mxs">
        {p.panels.map((pn, k) => (
          <div className="mx" key={`${k}${pn.label}`}>
            <div className="eyebrow">{pn.label}</div>
            <div className="mxg" style={{ gridTemplateColumns: `repeat(${nCols}, 1fr)` }}>
              {p.rows.flatMap((row, r) =>
                p.cols.map((col, c) => {
                  const v = pn.values[r]?.[c];
                  const ok = isNum(v);
                  const a = ok ? Math.sqrt(Math.max(0, v) / vmax) : 0;
                  return (
                    <i key={`${r}-${c}`} className={ok ? undefined : "na"}
                      style={ok ? { background: `rgba(${R},${G},${B},${a.toFixed(3)})` } : undefined}
                      title={`${row} × ${col}: ${ok ? Number(v.toPrecision(3)) : "n/a"}`} />
                  );
                }),
              )}
            </div>
          </div>
        ))}
      </div>
      <div className="wtype">{p.scale.label} · {p.rows.length} × {p.cols.length}</div>
    </div>
  );
}
