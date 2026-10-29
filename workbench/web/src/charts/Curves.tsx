// Curvas por x (perfis, espectros): faixa de referência, marcadores verticais e rótulos diretos no fim
// de cada série. Porta de docs/planning/mockups-v3/render_v3.py (curves_svg).
import type { CurvesPayload } from "../contract/types";
import { ticks } from "../contract/format";
import { spreadLabels } from "../components/labelSpread";
import { OTHER, SERIES } from "../palette";
import { fmt, isNum } from "./num";

interface Props {
  payload: CurvesPayload;
  colors?: Record<string, string>;
  width?: number;
  height?: number;
}

export const REAL_INK = "var(--ink2)";
const LABEL_GAP = 14;

/** Colour per series: the real series is ink; the rest follow the palette in order, `colors` wins. */
export function curveColors(series: CurvesPayload["series"], colors?: Record<string, string>): string[] {
  let k = 0;
  return series.map(s => {
    if (s.role === "real") return REAL_INK;
    const own = SERIES[k] ?? OTHER;
    k += 1;
    return colors?.[s.label] ?? own;
  });
}

export function Curves({ payload: p, colors, width: w = 560, height: h = 200 }: Props) {
  const logy = p.y.scale === "log";
  const logx = p.x.scale === "log";
  const okY = (v: number | null | undefined): v is number => isNum(v) && (!logy || v > 0);
  const okX = (v: number | null | undefined): v is number => isNum(v) && (!logx || v > 0);

  const xs = [...p.series.flatMap(s => s.x), ...(p.band?.x ?? [])].filter(okX);
  const ys = [...p.series.flatMap(s => s.y), ...(p.band ? [...p.band.lo, ...p.band.hi] : [])].filter(okY);
  const pl = 46, pr = 110, pt = 10, pb = 28;
  if (xs.length === 0 || ys.length === 0) {
    return (
      <svg className="spec chart-curves" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="xMidYMid meet">
        <text x={w / 2} y={h / 2} className="ax" textAnchor="middle">n/a</text>
      </svg>
    );
  }

  const tx = (v: number) => (logx ? Math.log10(v) : v);
  const x0 = Math.min(...xs.map(tx)), x1 = Math.max(...xs.map(tx));
  let lo: number, hi: number;
  if (logy) {
    lo = Math.floor(Math.log10(Math.min(...ys)));
    hi = Math.ceil(Math.log10(Math.max(...ys)));
    if (hi === lo) hi = lo + 1;
  } else {
    const yt = ticks(Math.min(0, ...ys), Math.max(...ys), 4);
    lo = yt[0];
    hi = yt[yt.length - 1];
  }
  const X = (v: number) => pl + ((tx(v) - x0) / (x1 - x0 || 1)) * (w - pl - pr);
  const Y = (v: number) => {
    const t = logy ? (Math.log10(Math.max(v, 10 ** lo)) - lo) / (hi - lo) : (v - lo) / (hi - lo || 1);
    return pt + (1 - t) * (h - pt - pb);
  };

  const yTicks = logy
    ? Array.from({ length: hi - lo + 1 }, (_, i) => lo + i)
    : ticks(lo, hi, 4).filter(t => t <= hi + 1e-9);
  const xTicks = logx
    ? Array.from({ length: Math.floor(x1) - Math.ceil(x0) + 1 }, (_, i) => 10 ** (Math.ceil(x0) + i))
    : ticks(x0, x1).filter(t => t >= x0 - 1e-9 && t <= x1 + 1e-9);

  let band: string | null = null;
  if (p.band) {
    const pts = p.band.x
      .map((x, i) => [x, p.band!.lo[i], p.band!.hi[i]] as const)
      .filter(([x, a, b]) => okX(x) && okY(a) && okY(b)) as [number, number, number][];
    if (pts.length > 1) {
      const top = pts.map(([x, , b]) => `${X(x).toFixed(1)},${Y(b).toFixed(1)}`);
      const bot = [...pts].reverse().map(([x, a]) => `${X(x).toFixed(1)},${Y(a).toFixed(1)}`);
      band = [...top, ...bot].join(" ");
    }
  }

  const palette = curveColors(p.series, colors);
  const lines = p.series.map((s, i) => {
    // pontos sem leitura quebram a linha; os demais mantêm a posição em x
    let d = "";
    let pen = false;
    let last: number | null = null;
    s.x.forEach((x, j) => {
      const y = s.y[j];
      if (!okX(x) || !okY(y)) {
        pen = false;
        return;
      }
      d += `${pen ? "L" : "M"}${X(x).toFixed(1)},${Y(y).toFixed(1)}`;
      pen = true;
      last = y;
    });
    return { s, d, color: palette[i], endY: last === null ? null : Y(last), delay: 0.15 * i };
  });
  const ended = lines.filter(l => l.endY !== null);
  const labelYs = spreadLabels(ended.map(l => l.endY!), LABEL_GAP);

  return (
    <svg className="spec chart-curves" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="xMidYMid meet">
      {yTicks.map(t => {
        const y = Y(logy ? 10 ** t : t);
        return (
          <g key={`y${t}`}>
            <line x1={pl} x2={w - pr} y1={y} y2={y} className="grid" />
            <text x={pl - 8} y={y + 4} className="ax" textAnchor="end">
              {logy ? (
                <>
                  10<tspan dy={-5} fontSize={8}>{t}</tspan>
                </>
              ) : (
                fmt(t)
              )}
            </text>
          </g>
        );
      })}
      {xTicks.map(t => (
        <text key={`x${t}`} x={X(t)} y={h - 12} className="ax" textAnchor="middle">
          {fmt(t)}
        </text>
      ))}
      <text x={(pl + w - pr) / 2} y={h} className="ax" textAnchor="middle">
        {p.x.label}
      </text>
      <text x={4} y={pt + (h - pt - pb) / 2} className="ax" textAnchor="middle"
        transform={`rotate(-90 4 ${pt + (h - pt - pb) / 2})`} dominantBaseline="hanging">
        {p.y.label}
      </text>
      {band && (
        <polygon points={band} className="band">
          <title>{p.band!.label}</title>
        </polygon>
      )}
      {p.markers.filter(m => okX(m.x)).map(m => (
        <line key={`m${m.x}${m.label}`} x1={X(m.x)} x2={X(m.x)} y1={pt} y2={h - pb} className="nyq">
          <title>{m.label}</title>
        </line>
      ))}
      {lines.map(({ s, d, color, delay }, i) => (
        <path key={`s${i}`} d={d} className="line" data-label={s.label}
          style={{ stroke: color, animationDelay: `${delay.toFixed(2)}s` }}>
          <title>{s.label}</title>
        </path>
      ))}
      {ended.map((l, i) => (
        <g key={`l${i}`}>
          <line x1={w - pr + 4} x2={w - pr + 12} y1={labelYs[i]} y2={labelYs[i]} style={{ stroke: l.color, strokeWidth: 2 }} />
          <text x={w - pr + 16} y={labelYs[i] + 4} className="lab">
            {l.s.label}
          </text>
        </g>
      ))}
    </svg>
  );
}
