// Tipos do contrato genérico do workbench (docs/planning/2026-10-27-workbench-generic-contract.md, §3–§5).
// Os nomes de campos seguem o JSON do contrato; números não finitos chegam como null.

/** Fixed wire vocabulary; labels come from `schema.statuses`. */
export type StatusKey = "approved" | "inconclusive" | "review" | "rejected";
export type Tone = "good" | "warn" | "bad" | "neutral";

// ---------------------------------------------------------------- §3 descriptors

export interface DatasetRef {
  key: string;
  label: string;
  mode_label: string;
  has_history: boolean;
}

export interface Noun {
  singular: string;
  plural: string;
}

export interface GroupBy {
  key: string;
  label: string;
  /** Caption shown with the grouped grid (e.g. members of a group are not independent). */
  note?: string | null;
}

export interface DatasetDesc {
  key: string;
  label: string;
  mode_label: string;
  item: Noun;
  group_by: GroupBy | null;
  reference_version: string;
  default_baseline: string;
}

export interface StatusDesc {
  key: StatusKey;
  label: string;
  tone: Tone;
  severity: number;
}

export interface AxisDesc {
  key: string;
  label: string;
  guide?: string;
}

export interface TechniqueDesc {
  key: string;
  label: string;
}

/** `abs_value` is also sent by the current adapter (|x| > limit). */
export type LimitKind = "abs_z" | "abs_value" | "above" | "below";

export interface Limits {
  review: number | null;
  reject: number | null;
  kind: LimitKind;
}

export interface MetricDesc {
  key: string;
  label: string;
  axis: string;
  technique: string;
  display: "z" | "value";
  unit: string;
  decimals: number;
  limits: Limits | null;
  repeatability: number | null;
  description?: string | null;
}

export type ChartKind = "curves" | "bars" | "interval" | "matrix" | "image";

export interface Choice {
  key: string;
  label: string;
}

export interface InspectorOption {
  key: string;
  label: string;
  choices: Choice[];
}

export interface InspectorDesc {
  key: string;
  label: string;
  chart: ChartKind;
  compare?: boolean;
  options?: InspectorOption[];
}

export interface IndicatorDesc {
  key: string;
  label: string;
  axis: string;
  unit: string;
  better?: "lower" | "higher" | "closer";
  ideal: number;
  min_change: number;
}

export interface CohortTestDesc {
  key: string;
  label: string;
  axis: string;
}

export interface Addons {
  optimizers: boolean;
  experiments: boolean;
}

export interface Schema {
  datasets: DatasetRef[];
  dataset: DatasetDesc;
  statuses: StatusDesc[];
  axes: AxisDesc[];
  techniques: TechniqueDesc[];
  metrics: MetricDesc[];
  inspectors: InspectorDesc[];
  indicators: IndicatorDesc[];
  cohort_tests: CohortTestDesc[];
  addons: Addons;
}

// ---------------------------------------------------------------- §4.1 items

export type Interval = [number | null, number | null];

export interface MetricValue {
  value: number | null;
  z: number | null;
  ci: Interval | null;
  real: number | null;
  synthetic: number | null;
  pct?: number | null;
  status: StatusKey;
  available: boolean;
}

export interface Reason {
  axis: string;
  metric: string;
  status: StatusKey;
  value: number | null;
  z: number | null;
  ci: Interval | null;
  limit: "review" | "reject" | null;
  limit_value: number | null;
  direction: "higher" | "lower" | null;
  note: string | null;
}

export interface Fact {
  label: string;
  value: string;
}

export interface Item {
  id: string;
  label: string;
  group: string | null;
  verdicts: Record<string, StatusKey>;
  techniques: Record<string, Record<string, StatusKey>>;
  metrics: Record<string, MetricValue>;
  reasons: Reason[];
  facts: Fact[];
}

export interface ItemsResponse {
  version: string;
  items: Item[];
}

// ---------------------------------------------------------------- §4.2 inspectors

export interface CurveSeries {
  label: string;
  role: "real" | "version" | "item";
  x: (number | null)[];
  y: (number | null)[];
}

export interface CurvesPayload {
  x: { label: string; scale?: "linear" | "log" };
  y: { label: string; scale: "linear" | "log" };
  band: { label: string; x: number[]; lo: (number | null)[]; hi: (number | null)[] } | null;
  markers: { x: number; label: string }[];
  series: CurveSeries[];
}

export interface Bar {
  label: string;
  value: number | null;
  ci?: Interval | null;
}

export interface BarsPayload {
  y: { label: string };
  zero: number;
  bars: Bar[];
  note?: string | null;
}

export interface IntervalBand {
  from: number;
  to: number;
  status: StatusKey;
}

export interface IntervalPayload {
  value: number | null;
  ci: Interval | null;
  label?: string;
  bands: IntervalBand[];
  // enviados pelos fixtures atuais além do contrato
  unit?: string;
  status?: StatusKey;
  note?: string | null;
}

export interface MatrixPanel {
  label: string;
  values: (number | null)[][];
}

export interface MatrixPayload {
  rows: string[];
  cols: string[];
  panels: MatrixPanel[];
  scale: { label: string };
}

export interface ImagePayload {
  url: string;
  caption: string;
}

export type InspectorPayload = CurvesPayload | BarsPayload | IntervalPayload | MatrixPayload | ImagePayload;

// ---------------------------------------------------------------- §4.3 board

export type GainResult = "improved" | "worse" | "same" | "small";

export interface VsBaseline {
  indicator: string;
  gain: number | null;
  ci: Interval | null;
  result: GainResult;
}

export interface CohortResult {
  test: string;
  result: { label: string; status: StatusKey };
  detail: Fact[];
}

export interface Provenance {
  run: string;
  step: number | string;
}

export interface BoardVersion {
  name: string;
  /** Display name of the version; the UI never shows `name`. */
  label: string;
  subtitle: string;
  is_reference: boolean;
  provenance: Provenance | null;
  counts: Record<string, Partial<Record<StatusKey, number>>>;
  vs_baseline: VsBaseline[] | null;
  cohort: CohortResult[];
  /** Per-indicator score `[value, low, high]` (95% CI); null when the indicator has no reading. */
  scores?: Record<string, (number | null)[] | null>;
}

export interface Board {
  n_items: number;
  baseline: string;
  versions: BoardVersion[];
}

export interface Transition {
  id: string;
  before: StatusKey;
  after: StatusKey;
  change: string;
  became_approved: boolean;
}

// ---------------------------------------------------------------- §4.4 runs

export interface RunSource {
  label: string;
  path: string;
  exists: boolean;
}

export interface RunParam {
  key: string;
  label: string;
  kind?: string;
}

export type ParamValue = number | string | boolean | null;

export interface Outcome {
  status: StatusKey;
  label: string;
}

export interface RunStep {
  id: string;
  stage: string | null;
  params: Record<string, ParamValue>;
  score: number | null;
  outcome: Outcome;
  wins: number | null;
  losses: number | null;
  is_best: boolean;
}

export interface Run {
  key: string;
  label: string;
  /** Legacy field still present in the real fixture; not part of the contract. */
  state?: string;
  summary: { best: number | null; evaluated: number; used: number; budget: number | null };
  best_params: Record<string, ParamValue>;
  curve: { x: number; y: number | null }[];
  steps: RunStep[];
}

export interface Runs {
  sources: RunSource[];
  objective: { label: string; unit: string; goal: number | null; higher_is_better: boolean };
  budget_axis: { label: string };
  params: RunParam[];
  runs: Run[];
}

// ---------------------------------------------------------------- §4.5 experiments

export interface Experiment {
  id: string;
  parent: string | null;
  change: string;
  outcome: Outcome;
  scores: Record<string, number | null>;
  is_best: boolean;
  note: string | null;
}

export interface ExperimentTable {
  title: string;
  for: string;
  columns: string[];
  rows: string[][];
}

export interface ExperimentSection {
  title: string;
  items: { head: string | null; body: string }[];
}

export interface Experiments {
  source: { label: string; path: string };
  objective: { label: string; unit: string; goal: number | null };
  scopes: { key: string; label: string }[];
  experiments: Experiment[];
  tables: ExperimentTable[];
  sections: ExperimentSection[];
}

// ---------------------------------------------------------------- §4.6 versions

export interface VersionInfo {
  name: string;
  label: string;
  is_reference: boolean;
  added: string;
  mode_label: string;
  n_items: number;
  n_common: number;
  warnings: { label: string; count: number }[];
  provenance: Provenance | null;
}

export interface DetectedRun {
  name: string;
  folder: string;
}
