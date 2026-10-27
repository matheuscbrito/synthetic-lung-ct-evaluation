// Barras a partir de uma linha de zero (razões, energias por banda). Porta de render_v3.py (bars_svg).
// Barra sem leitura mantém a posição e o rótulo, sem retângulo.
import type { BarsPayload } from "../contract/types";
import { fmt, isNum } from "./num";

interface Props {
  payload: BarsPayload;
  width?: number;
  height?: number;
}

export function Bars({ payload: p, width: w = 560, height: h = 200 }: Props) {
  const z = isNum(p.zero) ? p.zero : 0;
  const vals = [z];
  for (const b of p.bars) {
    if (isNum(b.value)) vals.push(b.value);
    if (b.ci && isNum(b.ci[0]) && isNum(b.ci[1])) vals.push(b.ci[0], b.ci[1]);
  }
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * 0.1 || 1;
  lo -= pad;
  hi += pad;
  const pl = 46, pr = 16, pt = 10, pb = 30;
  const Y = (v: number) => pt + ((hi - v) / (hi - lo)) * (h - pt - pb);
  const bw = (w - pl - pr) / Math.max(1, p.bars.length);

  return (
    <svg className="spec chart-bars" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
      <title>{p.y.label}</title>
      <line x1={pl} x2={w - pr} y1={Y(z)} y2={Y(z)} className="zero" />
      <text x={pl - 8} y={Y(z) + 4} className="ax" textAnchor="end">{fmt(z)}</text>
      {p.bars.map((b, i) => {
        const x = pl + i * bw + bw * 0.22;
        const cx = x + bw * 0.28;
        const has = isNum(b.value);
        const [y0, y1] = has ? [Y(z), Y(b.value!)].sort((a, c) => a - c) : [0, 0];
        const ci = b.ci && isNum(b.ci[0]) && isNum(b.ci[1]) ? [Y(b.ci[0]), Y(b.ci[1])] : null;
        return (
          <g key={`${i}${b.label}`}>
            {has && (
              <rect x={x} y={y0} width={bw * 0.56} height={Math.max(1, y1 - y0)} rx={4} className="wbar"
                style={{ animationDelay: `${(0.05 * i).toFixed(2)}s` }}>
                <title>{`${b.label}: ${b.value!.toFixed(2)}`}</title>
              </rect>
            )}
            {ci && <line x1={cx} x2={cx} y1={ci[0]} y2={ci[1]} className="whisk" />}
            {!has && (
              <text x={cx} y={Y(z) - 6} className="ax" textAnchor="middle">n/a</text>
            )}
            <text x={cx} y={h - 10} className="ax blab" textAnchor="middle">{b.label}</text>
          </g>
        );
      })}
    </svg>
  );
}
