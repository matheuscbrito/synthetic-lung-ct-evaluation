// Lógica pura do notebook de experimentos (contrato §4.5; porta de showX, lineage e drawTraj em
// docs/planning/mockups-v3/render_v3.py). Nada aqui conhece nomes de experimentos, escopos ou idiomas.
import type { Experiment } from "../contract/types";
import { ticks } from "../contract/format";

type ById = Record<string, Experiment> | Map<string, Experiment>;

function at(byId: ById, id: string): Experiment | undefined {
  if (byId instanceof Map) return byId.get(id);
  return Object.prototype.hasOwnProperty.call(byId, id) ? byId[id] : undefined;
}

/** Root first, `id` last, following `parent`. Stops at a missing parent and on a cycle. */
export function lineage(byId: ById, id: string): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  let cur = at(byId, id);
  while (cur && !seen.has(cur.id)) {
    seen.add(cur.id);
    out.unshift(cur.id);
    cur = cur.parent === null ? undefined : at(byId, cur.parent);
  }
  return out;
}

/** Score on the largest scope that has a finite value (scopes are listed smallest first); null when none. */
export function lastScore(exp: Experiment, scopes: { key: string }[] = []): number | null {
  const keys = scopes.length > 0 ? scopes.map(s => s.key) : Object.keys(exp.scores);
  let out: number | null = null;
  for (const k of keys) {
    const v = exp.scores[k];
    if (typeof v === "number" && Number.isFinite(v)) out = v;
  }
  return out;
}

/**
 * Trajectory of the chart: the lineage of the best experiment, then the lineage of the latest scored
 * experiment outside it. Only scored nodes stay in each path, in lineage order.
 */
export function trajectoryPaths(experiments: Experiment[], scopes: { key: string }[] = []): string[][] {
  const byId = new Map(experiments.map(e => [e.id, e]));
  const best = experiments.find(e => e.is_best);
  const onBest = new Set(best ? lineage(byId, best.id) : []);
  const ends: string[] = [];
  if (best) ends.push(best.id);
  const outside = experiments.filter(e => lastScore(e, scopes) !== null && !onBest.has(e.id));
  const other = outside[outside.length - 1];
  if (other) ends.push(other.id);
  return ends.map(id => lineage(byId, id).filter(x => lastScore(byId.get(x)!, scopes) !== null));
}

/** The experiment shown when the route names none (or one that does not exist): the best, else the last. */
export function selectedId(experiments: Experiment[], wanted: string | undefined): string | null {
  if (wanted !== undefined && experiments.some(e => e.id === wanted)) return wanted;
  return (experiments.find(e => e.is_best) ?? experiments[experiments.length - 1])?.id ?? null;
}

/** Case-insensitive filter over id, change, outcome label and note; an empty query keeps everything. */
export function filterExperiments(experiments: Experiment[], query: string): Experiment[] {
  const q = query.trim().toLocaleLowerCase();
  if (!q) return experiments;
  return experiments.filter(e =>
    [e.id, e.change, e.outcome.label, e.note ?? ""].some(text => text.toLocaleLowerCase().includes(q)),
  );
}

/** Chart box in pixels; `left`/`right`/`top`/`bottom` are the margins around the plot. */
export interface ChartBox {
  width: number;
  height: number;
  left: number;
  right: number;
  top: number;
  bottom: number;
}

export interface TrajPoint {
  id: string;
  x: number;
  y: number;
  value: number;
}

export interface TrajLayout {
  /** Gridline values; the first is at or below the lowest value, the last at or above the highest. */
  ticks: number[];
  /** Goal line position, null when the objective has no goal. */
  goalY: number | null;
  /** Pixel y of a value on this scale. */
  y: (v: number) => number;
  paths: TrajPoint[][];
}

/**
 * Plot geometry of the trajectory: one x step per path position (item order kept), y from the scored values
 * and the goal. Experiments without a score never reach a point, so they never shift the scale.
 */
export function trajectoryLayout(
  experiments: Experiment[],
  paths: string[][],
  scopes: { key: string }[],
  goal: number | null,
  box: ChartBox,
): TrajLayout {
  const byId = new Map(experiments.map(e => [e.id, e]));
  const values = experiments.map(e => lastScore(e, scopes)).filter((v): v is number => v !== null);
  const lo = Math.min(0, ...values);
  const hi = Math.max(0, goal ?? 0, ...values) * 1.1;
  const grid = ticks(lo, hi, 4);
  const ymin = grid.length ? grid[0] : lo;
  let ymax = grid.length ? grid[grid.length - 1] : hi;
  if (ymax <= ymin) ymax = ymin + 1;
  const n = Math.max(2, ...paths.map(p => p.length));
  const X = (i: number) => box.left + (i / (n - 1)) * (box.width - box.left - box.right);
  const Y = (v: number) => box.top + (1 - (v - ymin) / (ymax - ymin)) * (box.height - box.top - box.bottom);
  return {
    ticks: grid,
    goalY: goal === null ? null : Y(goal),
    y: Y,
    paths: paths.map(p =>
      p.map((id, i) => {
        const value = lastScore(byId.get(id)!, scopes)!;
        return { id, x: X(i), y: Y(value), value };
      }),
    ),
  };
}
