// Lógica pura do benchmark de geradores (contrato §4.3; porta de slide_bench em docs/planning/mockups-v3/render_v3.py).
// Nada aqui conhece nomes de eixos, indicadores ou versões: tudo vem do esquema e do placar.
import type { Addons, Board, BoardVersion, GainResult, Schema, StatusKey, Tone, Transition, VsBaseline } from "../contract/types";
import type { Tab } from "../route";

/** Board row as the API sends it: `label` and per-indicator `scores` ([value, low, high]) beside the §4.3 fields. */
export interface BenchVersion extends BoardVersion {
  label?: string;
  scores?: Record<string, (number | null)[] | null>;
}

/** Board as the API sends it (rows carry `label` and `scores`). */
export interface BenchBoard extends Omit<Board, "versions"> {
  versions: BenchVersion[];
}

export type GeneratorTab = Extract<Tab, "bench" | "runs" | "exp">;

/** Generators tabs: Benchmark always; Optimizers and Notebook only when `addons` says so. */
export function generatorTabs(addons: Addons): { value: GeneratorTab; label: string }[] {
  return [
    { value: "bench" as const, label: "Benchmark" },
    ...(addons.optimizers ? [{ value: "runs" as const, label: "Optimizers" }] : []),
    ...(addons.experiments ? [{ value: "exp" as const, label: "Notebook" }] : []),
  ];
}

export interface TransitionSummary {
  worsened: number;
  improved: number;
  becameApproved: number;
}

export function transitionSummary(t: Transition[]): TransitionSummary {
  let worsened = 0;
  let improved = 0;
  let becameApproved = 0;
  for (const x of t) {
    if (x.change === "worsened") worsened += 1;
    else if (x.change === "improved") improved += 1;
    if (x.became_approved) becameApproved += 1;
  }
  return { worsened, improved, becameApproved };
}

export type TransitionFilter = "all" | "improved" | "worsened" | "became";

/** `all` lists every item whose verdict changed; the others are subsets of it. */
export function filterTransitions(t: Transition[], filter: TransitionFilter): Transition[] {
  switch (filter) {
    case "improved":
      return t.filter(x => x.change === "improved");
    case "worsened":
      return t.filter(x => x.change === "worsened");
    case "became":
      return t.filter(x => x.became_approved);
    default:
      return t.filter(x => x.change !== "same");
  }
}

const CHANGE_RANK: Record<string, number> = { worsened: 0, improved: 1, same: 2 };

function severity(schema: Schema, status: StatusKey): number {
  return schema.statuses.find(s => s.key === status)?.severity ?? 0;
}

/** Worst first: worsened (most severe new status first), improved, unchanged; ties by id (code-point order). */
export function orderTransitions(t: Transition[], schema: Schema): Transition[] {
  return [...t].sort(
    (a, b) =>
      (CHANGE_RANK[a.change] ?? 3) - (CHANGE_RANK[b.change] ?? 3) ||
      (a.change === "worsened" ? severity(schema, b.after) - severity(schema, a.after) : 0) ||
      (a.id < b.id ? -1 : a.id > b.id ? 1 : 0),
  );
}

/**
 * Version compared with the baseline: the route's when it exists and is not the baseline,
 * else the newest version that is neither the reference nor the baseline, else any other version.
 */
export function defaultCurrent(versions: BoardVersion[], baseline: string, wanted: string | undefined): string | undefined {
  const others = versions.filter(v => v.name !== baseline);
  if (wanted && others.some(v => v.name === wanted)) return wanted;
  const synth = others.filter(v => !v.is_reference);
  return (synth[synth.length - 1] ?? others[others.length - 1])?.name;
}

/** Baseline row first, then the board order. */
export function orderVersions<V extends BoardVersion>(versions: V[], baseline: string): V[] {
  return [...versions.filter(v => v.name === baseline), ...versions.filter(v => v.name !== baseline)];
}

/** Status chips shown per axis cell: statuses by severity that have a count somewhere on the board. */
export function axisStatuses(versions: BoardVersion[], schema: Schema): StatusKey[] {
  return [...schema.statuses]
    .sort((a, b) => a.severity - b.severity)
    .map(s => s.key)
    .filter(k => versions.some(v => Object.values(v.counts).some(c => (c[k] ?? 0) > 0)));
}

/** Above this many axes the table shows one stacked status bar per axis instead of chips (contract §5). */
export const CHIP_AXES_MAX = 4;

/** Indicators with a clear difference versus the baseline. */
export function clearDifferences(v: BoardVersion): VsBaseline[] {
  return (v.vs_baseline ?? []).filter(x => x.result === "improved" || x.result === "worse");
}

const RESULT_TONE: Record<GainResult, Tone> = { improved: "good", worse: "bad", same: "neutral", small: "neutral" };

/** Status whose tone colours a gain result (improved → good, worse → bad, else neutral). */
export function resultStatus(result: GainResult, schema: Schema): StatusKey {
  const tone = RESULT_TONE[result] ?? "neutral";
  return schema.statuses.find(s => s.tone === tone)?.key ?? "inconclusive";
}

export const RESULT_LABEL: Record<GainResult, string> = {
  improved: "improved",
  worse: "worse",
  same: "no clear difference",
  small: "small change",
};

const finite = (x: number | null | undefined): x is number => typeof x === "number" && Number.isFinite(x);

/** Decimals for an indicator, from its smallest meaningful change (5 → 1, 0.2 → 2, 0.05 → 3). */
export function indicatorDecimals(minChange: number | null | undefined): number {
  if (!finite(minChange) || minChange <= 0) return 2;
  if (minChange >= 1) return 1;
  return minChange >= 0.1 ? 2 : 3;
}

/** `value [low, high]`; `n/a` without a value; the interval only when both ends are finite. */
export function scoreText(score: (number | null)[] | null | undefined, d: number): string {
  const [v, lo, hi] = score ?? [];
  if (!finite(v)) return "n/a";
  const ci = finite(lo) && finite(hi) ? ` [${lo.toFixed(d)}, ${hi.toFixed(d)}]` : "";
  return `${v.toFixed(d)}${ci}`;
}
