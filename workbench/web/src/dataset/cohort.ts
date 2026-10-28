// Dados das visões de coorte da visão geral (gráficos, matriz de vereditos e tabela), porta genérica dos
// gráficos de coorte, da matriz e das tabelas técnicas da interface antiga (paridade #18–21, 26, 29–35,
// 41, 46–47, 49, 55, 73–74, 81–82). Nada aqui conhece nomes de métricas: tudo vem do descritor.
import { metricDeviation, orderItems, reasonText } from "../contract/format";
import type { Item, MetricDesc, MetricValue, Schema, StatusKey } from "../contract/types";
import { axisTechniques } from "./strip";

const finite = (x: number | null | undefined): x is number => typeof x === "number" && Number.isFinite(x);
const byId = (a: Item, b: Item) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);

/** Fraction of the span added past the data and the limits, so the outer band stays visible. */
const PAD = 0.08;

// ------------------------------------------------------------------ strip chart

export interface CohortPoint {
  /** Position of the item in the list given (kept when other items have no reading). */
  index: number;
  id: string;
  y: number;
  lo: number | null;
  hi: number | null;
  status: StatusKey;
}

export interface CohortBand {
  from: number;
  to: number;
  status: StatusKey;
}

export interface CohortSeries {
  points: CohortPoint[];
  bands: CohortBand[];
  domain: [number, number];
}

/** Plotted reading of a metric: z for z metrics, value otherwise; null when unread or unavailable. */
export function plotted(m: MetricDesc, v: MetricValue | undefined): { y: number; lo: number | null; hi: number | null } | null {
  if (!v || v.available === false) return null;
  const y = m.display === "z" ? v.z : v.value;
  if (!finite(y)) return null;
  const ci = v.ci && finite(v.ci[0]) && finite(v.ci[1]) ? v.ci : null;
  return { y, lo: ci ? ci[0] : null, hi: ci ? ci[1] : null };
}

function points(items: Item[], m: MetricDesc): CohortPoint[] {
  const out: CohortPoint[] = [];
  items.forEach((it, index) => {
    const v = it.metrics[m.key];
    const p = plotted(m, v);
    if (p) out.push({ index, id: it.id, ...p, status: v!.status });
  });
  return out;
}

/** Limit values that must stay inside the domain (±limits for |x| kinds, 0 and the limits otherwise). */
function limitEdges(m: MetricDesc): number[] {
  const L = m.limits;
  if (!L) return [];
  const lim = [L.review, L.reject].filter(finite);
  if (L.kind === "abs_z" || L.kind === "abs_value") return lim.flatMap(x => [-x, x]);
  return [0, ...lim];
}

function domainOf(m: MetricDesc, series: CohortPoint[][]): [number, number] {
  const values = series.flat().flatMap(p => [p.y, p.lo, p.hi]).filter(finite);
  const all = [...values, ...limitEdges(m)];
  let lo = all.length ? Math.min(...all) : -1;
  let hi = all.length ? Math.max(...all) : 1;
  const symmetric = m.limits?.kind === "abs_z" || m.limits?.kind === "abs_value";
  if (symmetric) {
    const r = Math.max(Math.abs(lo), Math.abs(hi)) || 1;
    return [-r * (1 + PAD), r * (1 + PAD)];
  }
  const span = hi - lo || Math.abs(hi) || 1;
  // um limite "acima de" parte do zero: não desce abaixo dele se nenhum dado desce
  lo = lo >= 0 ? lo : lo - span * PAD;
  hi = hi + span * PAD;
  return [lo, hi];
}

function bandsOf(m: MetricDesc, [lo, hi]: [number, number]): CohortBand[] {
  const L = m.limits;
  if (!L) return [];
  const R = finite(L.review) ? L.review : null;
  const J = finite(L.reject) ? L.reject : null;
  let out: CohortBand[];
  if (L.kind === "abs_z" || L.kind === "abs_value") {
    const inner = R ?? J;
    if (inner === null) return [];
    const outer = R !== null && J !== null && J > R ? J : null;
    const outerStatus: StatusKey = R === null ? "rejected" : "review";
    out = outer !== null
      ? [
          { from: lo, to: -outer, status: "rejected" },
          { from: -outer, to: -inner, status: "review" },
          { from: -inner, to: inner, status: "approved" },
          { from: inner, to: outer, status: "review" },
          { from: outer, to: hi, status: "rejected" },
        ]
      : [
          { from: lo, to: -inner, status: outerStatus },
          { from: -inner, to: inner, status: "approved" },
          { from: inner, to: hi, status: outerStatus },
        ];
  } else if (L.kind === "above") {
    const steps: [number, StatusKey][] = [];
    if (R !== null) steps.push([R, "review"]);
    if (J !== null && (R === null || J > R)) steps.push([J, "rejected"]);
    out = [];
    let from = Math.min(0, lo);
    let status: StatusKey = "approved";
    for (const [edge, next] of steps) {
      out.push({ from, to: edge, status });
      from = edge;
      status = next;
    }
    out.push({ from, to: hi, status });
  } else {
    // "below": abaixo do limite é ruim
    const steps: [number, StatusKey][] = [];
    if (J !== null) steps.push([J, "rejected"]);
    if (R !== null && (J === null || R > J)) steps.push([R, "review"]);
    out = [];
    let from = lo;
    for (const [edge, status] of steps) {
      out.push({ from, to: edge, status });
      from = edge;
    }
    out.push({ from, to: hi, status: "approved" });
  }
  return out.filter(b => b.to > b.from);
}

/**
 * Strip chart of one metric over the items, in the order given. Items without a reading are skipped but
 * the others keep their index. With `compareItems` the domain covers both versions (same axis side by side).
 */
export function cohortSeries(items: Item[], metric: MetricDesc, _schema: Schema, compareItems?: Item[]): CohortSeries {
  const own = points(items, metric);
  const domain = domainOf(metric, compareItems ? [own, points(compareItems, metric)] : [own]);
  return { points: own, bands: bandsOf(metric, domain), domain };
}

// ------------------------------------------------------------------ real × synthetic scatter

export interface ScatterPoint {
  index: number;
  id: string;
  x: number;
  y: number;
  status: StatusKey;
}

export interface ScatterSeries {
  points: ScatterPoint[];
  /** Smallest and largest reading over both versions (shared scale). */
  min: number;
  max: number;
}

function scatterPoints(items: Item[], m: MetricDesc): ScatterPoint[] {
  const out: ScatterPoint[] = [];
  items.forEach((it, index) => {
    const v = it.metrics[m.key];
    if (!v || v.available === false || !finite(v.real) || !finite(v.synthetic)) return;
    out.push({ index, id: it.id, x: v.real, y: v.synthetic, status: v.status });
  });
  return out;
}

/** Real (x) against synthetic (y) for items with both readings; min/max shared with `compareItems`. */
export function scatterSeries(items: Item[], metric: MetricDesc, compareItems?: Item[]): ScatterSeries {
  const own = scatterPoints(items, metric);
  const all = [...own, ...(compareItems ? scatterPoints(compareItems, metric) : [])].flatMap(p => [p.x, p.y]);
  return { points: own, min: all.length ? Math.min(...all) : 0, max: all.length ? Math.max(...all) : 1 };
}

/** Whether any item has both a real and a synthetic reading of the metric. */
export function hasScatter(items: Item[], metric: MetricDesc): boolean {
  return scatterPoints(items, metric).length > 0;
}

// ------------------------------------------------------------------ verdict matrix

export interface MatrixCell {
  id: string;
  label: string;
  status: StatusKey | null;
  /** Tooltip: reason sentences, or the status label when nothing is out of range. */
  title: string;
}

export interface MatrixRow {
  /** `verdict` for the axis row, else the technique key. */
  key: string;
  label: string;
  cells: MatrixCell[];
}

function statusLabel(schema: Schema, s: StatusKey | null | undefined): string {
  if (!s) return "n/a";
  return schema.statuses.find(x => x.key === s)?.label ?? s;
}

function reasonsOf(item: Item, axis: string, schema: Schema, technique?: string): string[] {
  const out: string[] = [];
  for (const r of item.reasons) {
    if (r.axis !== axis) continue;
    const desc = schema.metrics.find(m => m.key === r.metric);
    if (!desc) continue;
    if (technique !== undefined && desc.technique !== technique) continue;
    out.push(reasonText(desc, r));
  }
  return out;
}

/** Verdict row of the axis, then one row per technique; cells follow the order of `items`. */
export function matrixRows(items: Item[], axis: string, schema: Schema): MatrixRow[] {
  const axisLabel = schema.axes.find(a => a.key === axis)?.label ?? axis;
  const cell = (it: Item, status: StatusKey | null, reasons: string[], what: string): MatrixCell => ({
    id: it.id,
    label: it.label,
    status,
    title: [`${it.label} · ${what}: ${statusLabel(schema, status)}`, ...reasons].join("\n"),
  });
  const verdict: MatrixRow = {
    key: "verdict",
    label: axisLabel,
    cells: items.map(it => cell(it, it.verdicts[axis] ?? null, reasonsOf(it, axis, schema), axisLabel)),
  };
  const techniques = axisTechniques(items, axis, schema).map(t => ({
    key: t.key,
    label: t.label,
    cells: items.map(it => cell(it, it.techniques[axis]?.[t.key] ?? null, reasonsOf(it, axis, schema, t.key), t.label)),
  }));
  return [verdict, ...techniques];
}

/** Items of `other` in the order of `first` (items missing from `other` are dropped). */
export function alignTo(first: Item[], other: Item[]): Item[] {
  const byKey = new Map(other.map(it => [it.id, it]));
  return first.flatMap(it => {
    const o = byKey.get(it.id);
    return o ? [o] : [];
  });
}

// ------------------------------------------------------------------ table

export interface TableSort {
  /** `name`, `verdict`, `t:<technique>`, `m:<metric>` or `f:<fact label>`. */
  key: string;
  desc: boolean;
}

function severity(schema: Schema, s: StatusKey | undefined): number {
  return schema.statuses.find(x => x.key === s)?.severity ?? -1;
}

/** Table order: severity then spread (`orderItems`) by default, else by the chosen column. */
export function tableOrder(items: Item[], axis: string, schema: Schema, sort: TableSort | null): Item[] {
  if (!sort || sort.key === "verdict") {
    const out = orderItems(items, axis, schema);
    return sort?.desc === false ? out.reverse() : out;
  }
  const dir = sort.desc ? -1 : 1;
  const cmpStr = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);
  let key: (it: Item) => number | string | null;
  if (sort.key === "name") key = it => it.label;
  else if (sort.key.startsWith("t:")) {
    const t = sort.key.slice(2);
    key = it => severity(schema, it.techniques[axis]?.[t]);
  } else if (sort.key.startsWith("m:")) {
    const m = schema.metrics.find(x => x.key === sort.key.slice(2));
    key = it => (m ? metricDeviation(m, it.metrics[m.key]) : null);
  } else if (sort.key.startsWith("f:")) {
    const label = sort.key.slice(2);
    key = it => {
      const v = it.facts.find(f => f.label === label)?.value ?? null;
      const n = v === null ? NaN : Number(v);
      return v === null ? null : Number.isFinite(n) ? n : v;
    };
  } else return orderItems(items, axis, schema);
  // sem leitura vai sempre para o fim; empate pelo id
  return [...items].sort((a, b) => {
    const ka = key(a), kb = key(b);
    if (ka === null || kb === null) return ka === kb ? byId(a, b) : ka === null ? 1 : -1;
    const c = typeof ka === "number" && typeof kb === "number" ? ka - kb : cmpStr(String(ka), String(kb));
    return c * dir || byId(a, b);
  });
}

/** Fact labels carried by the items, in first-seen order. */
export function factLabels(items: Item[]): string[] {
  const out: string[] = [];
  for (const it of items) for (const f of it.facts) if (!out.includes(f.label)) out.push(f.label);
  return out;
}
