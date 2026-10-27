// Valor com IC sobre faixas de status (limiares de decisão). Porta de render_v3.py (interval_svg).
import type { IntervalPayload, StatusKey } from "../contract/types";
import { signed } from "../contract/format";
import { fmt, isNum, STATUS_DOT, STATUS_FILL } from "./num";

interface Props {
  payload: IntervalPayload;
  width?: number;
  height?: number;
}

/** Status of the point: the payload's own, else the band containing the value. */
export function pointStatus(p: IntervalPayload): StatusKey | null {
  if (p.status) return p.status;
  if (!isNum(p.value)) return null;
  const v = p.value;
  const inside = p.bands.find(b => v >= b.from && v <= b.to);
  if (inside) return inside.status;
  // fora das faixas: a da ponta mais próxima (o ponto é desenhado preso à borda)
  const sorted = [...p.bands].sort((a, b) => a.from - b.from);
  if (sorted.length === 0) return null;
  return v < sorted[0].from ? sorted[0].status : sorted[sorted.length - 1].status;
}

export function Interval({ payload: p, width: w = 560, height: h = 150 }: Props) {
  const edges = p.bands.flatMap(b => [b.from, b.to]).filter(isNum);
  const lo = edges.length ? Math.min(...edges) : -1;
  const hi = edges.length ? Math.max(...edges) : 1;
  const pl = 20, pr = 20, pt = 14, pb = 30;
  const X = (v: number) => pl + ((Math.min(hi, Math.max(lo, v)) - lo) / (hi - lo || 1)) * (w - pl - pr);
  const ys = pt + 10;
  const yh = h - pt - pb - 10;
  const cy = ys + yh / 2;
  const ci = p.ci && isNum(p.ci[0]) && isNum(p.ci[1]) ? ([p.ci[0], p.ci[1]] as const) : null;
  const status = pointStatus(p);
  const unit = p.unit ?? "";
  const valueText = isNum(p.value)
    ? `${signed(p.value, 2)}${unit ? ` ${unit}` : ""}${ci ? ` · [${signed(ci[0], 2)}, ${signed(ci[1], 2)}]` : ""}`
    : "n/a";
  const labelX = isNum(p.value) ? X(p.value) : (pl + w - pr) / 2;

  return (
    <svg className="spec chart-interval" viewBox={`0 0 ${w} ${h}`} style={{ height: h }}>
      {p.label && <title>{p.label}</title>}
      {p.bands.map((b, i) => (
        <rect key={i} className="iband" data-status={b.status} x={X(b.from)} y={ys}
          width={Math.max(0, X(b.to) - X(b.from))} height={yh} fill={STATUS_FILL[b.status]} />
      ))}
      {[...new Set(edges)].sort((a, b) => a - b).map(v => (
        <text key={v} x={X(v)} y={h - 10} className="ax" textAnchor="middle">{fmt(v)}</text>
      ))}
      {ci && (
        <g className="ci">
          <line x1={X(ci[0])} x2={X(ci[1])} y1={cy} y2={cy} />
          <line x1={X(ci[0])} x2={X(ci[0])} y1={cy - 8} y2={cy + 8} />
          <line x1={X(ci[1])} x2={X(ci[1])} y1={cy - 8} y2={cy + 8} />
        </g>
      )}
      {isNum(p.value) && (
        <circle className="pt" data-status={status ?? undefined} cx={X(p.value)} cy={cy} r={6.5}
          fill={status ? STATUS_DOT[status] : "var(--ink3)"} stroke="#fff" strokeWidth={2} />
      )}
      <text x={labelX} y={pt + 2} className="lab" textAnchor="middle">{valueText}</text>
    </svg>
  );
}
