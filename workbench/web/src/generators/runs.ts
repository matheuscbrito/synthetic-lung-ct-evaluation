// Lógica pura do Optimizers (contrato §4.4; porta de slide_runs e run_curve em docs/planning/mockups-v3/render_v3.py).
// Nada aqui conhece nomes de parâmetros ou de otimizadores: colunas e rótulos vêm de `params` e `runs`.
import { signed } from "../contract/format";
import type { Run, RunParam } from "../contract/types";
import { OTHER, SERIES } from "../palette";

export interface RankedRun {
  key: string;
  label: string;
  /** Colour by the run's position in the API list (never by rank). */
  color: string;
  best: number | null;
  /** First budget whose score reaches `best`; null when the curve never does. */
  toBest: number | null;
  evaluated: number;
  used: number;
}

/** First curve `x` whose score reaches the run's best (tolerance as in render_v3). */
export function reachX(run: Run): number | null {
  const best = run.summary.best;
  if (best === null || !Number.isFinite(best)) return null;
  const hit = run.curve.find(p => p.y !== null && p.y >= best - 1e-9);
  return hit ? hit.x : null;
}

/** Runs sorted by best score, highest first; a run without a best goes last. Ties keep the API order. */
export function rankRuns(runs: Run[]): RankedRun[] {
  const rows = runs.map((run, index) => ({
    index,
    row: {
      key: run.key,
      label: run.label,
      color: SERIES[index] ?? OTHER,
      best: run.summary.best,
      toBest: reachX(run),
      evaluated: run.summary.evaluated,
      used: run.summary.used,
    },
  }));
  rows.sort((a, b) => {
    const x = a.row.best;
    const y = b.row.best;
    if (x === null && y === null) return a.index - b.index;
    if (x === null) return 1;
    if (y === null) return -1;
    return y - x || a.index - b.index;
  });
  return rows.map(r => r.row);
}

export interface StepColumns {
  /** Stage column only when some step names a stage. */
  stage: boolean;
  /** W / L column only when some step reports wins or losses. */
  wl: boolean;
  /** Parameter columns: the declared parameters that at least one step of this run carries. */
  params: RunParam[];
}

export function stepColumns(run: Run, params: RunParam[]): StepColumns {
  return {
    stage: run.steps.some(s => !!s.stage),
    wl: run.steps.some(s => s.wins != null || s.losses != null),
    params: params.filter(p => run.steps.some(s => p.key in s.params)),
  };
}

/** Parameter value as text: numbers like Python's `:g`, missing values as an en dash. */
export function paramText(value: unknown): string {
  if (value === null || value === undefined) return "–";
  if (typeof value === "number") return Number.isFinite(value) ? String(Number(value.toPrecision(6))) : "–";
  return String(value);
}

/** Unit as printed after a number: `%` attached, other units spaced, nothing when empty. */
export function unitSuffix(unit: string): string {
  return !unit ? "" : unit === "%" ? "%" : ` ${unit}`;
}

/** Score with one decimal and the objective unit; `n/a` without a reading. */
export function runScore(score: number | null, unit: string): string {
  if (score === null || !Number.isFinite(score)) return "n/a";
  return `${signed(score, 1)}${unitSuffix(unit)}`;
}
