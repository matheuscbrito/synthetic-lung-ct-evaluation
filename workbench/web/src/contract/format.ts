// Formatação genérica do contrato; porta de docs/planning/mockups-v3/render_v3.py
// (sg, metric_text, limit_txt, reason_text, ticks, worst, order). Nada aqui conhece nomes de métricas.
import type { Item, MetricDesc, MetricValue, Reason, Schema, StatusKey, Tone } from "./types";

const MINUS = "−";
const DASH = "–";

/** Signed number with `d` decimals, U+2212 minus; values that round to zero print unsigned. */
export function signed(x: number, d: number): string {
  const body = Math.abs(x).toFixed(d);
  if (Number(body) === 0) return (0).toFixed(d);
  return (x < 0 ? MINUS : "+") + body;
}

/** Python's `:g` (6 significant digits, trailing zeros dropped). */
function g(x: number): string {
  return String(Number(x.toPrecision(6)));
}

const finite = (x: number | null | undefined): x is number => typeof x === "number" && Number.isFinite(x);

function unitSuffix(unit: string | null | undefined): string {
  if (!unit) return "";
  return unit === "%" ? "%" : ` ${unit}`;
}

/** Row text of one metric reading: `n/a` when missing; z with unit and CI; or value with unit. */
export function metricText(desc: MetricDesc, v: MetricValue | undefined): string {
  if (!v || v.available === false) return "n/a";
  const d = desc.decimals ?? 2;
  if (desc.display === "z" && finite(v.z)) {
    let t = `${signed(v.z, d)} ${desc.unit}`;
    if (v.ci && finite(v.ci[0]) && finite(v.ci[1])) t += ` [${signed(v.ci[0], d)}, ${signed(v.ci[1], d)}]`;
    return t;
  }
  if (!finite(v.value)) return "n/a";
  return `${v.value.toFixed(d)}${unitSuffix(desc.unit)}`;
}

const LIMIT_SYMBOL: Record<string, string> = { abs_z: "|z| > ", abs_value: "|x| > ", above: "> ", below: "< " };

/** Threshold text for the "How to read" table. */
export function limitText(desc: MetricDesc, which: "review" | "reject"): string {
  const L = desc.limits;
  const value = L?.[which];
  if (!L || !finite(value)) return DASH;
  const pct = L.kind !== "abs_z" && desc.unit === "%" ? "%" : "";
  return `${LIMIT_SYMBOL[L.kind] ?? ""}${g(value)}${pct}`;
}

/** One sentence per reason: note, z deviation, value above or below a limit. Never prints null values. */
export function reasonText(desc: MetricDesc, r: Reason): string {
  const d = desc.decimals ?? 2;
  if (r.note) return `${desc.label}: ${r.note}.`;
  const lim = r.limit ?? "review";
  const thr = finite(r.limit_value) ? r.limit_value : desc.limits?.[lim];
  if (finite(r.z)) {
    const ci = r.ci && finite(r.ci[0]) && finite(r.ci[1]) ? ` [${signed(r.ci[0], d)}, ${signed(r.ci[1], d)}]` : "";
    const dir = r.direction ? `${r.direction} than real` : "off from real";
    const past = finite(thr) ? `past the ${lim} limit (${g(thr)})` : `past the ${lim} limit`;
    return `${desc.label} is ${dir}: ${signed(r.z, d)} ${desc.unit}${ci}, ${past}.`;
  }
  const unit = unitSuffix(desc.unit);
  const side = r.direction !== "lower" ? "above" : "below";
  const limitPart = finite(thr) ? `the ${lim} limit (${g(thr)}${unit})` : `the ${lim} limit`;
  if (!finite(r.value)) return `${desc.label} is ${side} ${limitPart}.`;
  return `${desc.label} reads ${r.value.toFixed(d)}${unit}, ${side} ${limitPart}.`;
}

/**
 * Round tick values covering [lo, hi] with steps 1/2/2.5/5/10 × 10^k.
 * Default n = 6 (render_v3 uses 5); chosen so that ticks(0, 269) steps by 50 as the plan requires.
 */
export function ticks(lo: number, hi: number, n = 6): number[] {
  const raw = (hi - lo) / n || 1;
  const e = 10 ** Math.floor(Math.log10(Math.abs(raw)));
  const step = [1, 2, 2.5, 5, 10].map((k) => k * e).find((s) => s >= Math.abs(raw)) ?? 10 * e;
  const out: number[] = [];
  for (let t = Math.floor(lo / step) * step; t < hi + step - step * 1e-9; t += step) {
    out.push(Math.round(t * 1e10) / 1e10 + 0);
  }
  return out;
}

export function toneOf(schema: Schema, status: StatusKey): Tone {
  return schema.statuses.find((s) => s.key === status)?.tone ?? "neutral";
}

function severity(schema: Schema, status: StatusKey | undefined): number {
  return schema.statuses.find((s) => s.key === status)?.severity ?? 0;
}

/**
 * Deviation of one reading, normalised: |z|, or |value| ÷ review limit; with only a reject limit, the reject
 * limit reads 2 (as on the |z| scale, review 1 and reject 2). Null when unread, unavailable or without limits.
 */
export function metricDeviation(desc: MetricDesc, v: MetricValue | undefined): number | null {
  if (!v || v.available === false) return null;
  if (finite(v.z)) return Math.abs(v.z);
  if (!finite(v.value)) return null;
  const review = desc.limits?.review;
  if (finite(review) && review !== 0) return Math.abs(v.value) / review;
  const reject = desc.limits?.reject;
  if (finite(reject) && reject !== 0) return (2 * Math.abs(v.value)) / reject;
  return null;
}

/** Largest normalised deviation of an item on an axis (largest `metricDeviation`, 0 when none is read). */
export function worst(item: Item, axis: string, schema: Schema): number {
  let out = 0;
  for (const m of schema.metrics) {
    if (m.axis !== axis) continue;
    const d = metricDeviation(m, item.metrics[m.key]);
    if (d !== null) out = Math.max(out, d);
  }
  return out;
}

/** Severity desc, worst deviation desc, then id (code-point order, as in Python). */
export function orderItems(items: Item[], axis: string, schema: Schema): Item[] {
  const keyed = items.map((it) => ({ it, s: severity(schema, it.verdicts[axis]), w: worst(it, axis, schema) }));
  keyed.sort((a, b) => b.s - a.s || b.w - a.w || (a.it.id < b.it.id ? -1 : a.it.id > b.it.id ? 1 : 0));
  return keyed.map((k) => k.it);
}
