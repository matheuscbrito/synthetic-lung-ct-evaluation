// Tipos espelham o JSON de workbench/api (app.py, data.py, tools.py, board.py).

export type Status = "approved" | "review" | "rejected" | "inconclusive";
export type Verdict = "brightness" | "texture";
export type ResultLabel = "improved" | "worse" | "small change" | "no clear difference" | "n/a";

export interface ServerStatus {
  stale: boolean;
  has_history: boolean;
  baseline: string | null;
}

export interface Version {
  name: string;
  mode: string;
  n_cases: number;
  folder: string;
  added: string;
  is_baseline: boolean;
}

export interface Metric {
  key: string;
  label: string;
  group: Verdict;
  technique: string;
  real: number | null;
  synthetic: number | null;
  value: number | null;
  z: number | null;
  status: Status;
  unit: string;
}

export interface VerdictBlock {
  verdict: Status;
  techniques: Record<string, Status>;
}

export interface Slice {
  case_id: string;
  label: string;
  patient: string;
  pair_mode: string;
  brightness: VerdictBlock;
  texture: VerdictBlock;
  metrics: Metric[];
  density: { status: string; median_shift_iqr: number | null };
  wavelet_type: string;
}

export interface SlicesResponse {
  version: string;
  n_cases: number;
  slices: Slice[];
}

type Counts = Record<"approved" | "review" | "rejected", number>;

export interface VsBaseline {
  indicator: string;
  label: string;
  gain: number | null;
  ci: [number | null, number | null];
  result: ResultLabel;
}

export interface Generator {
  name: string;
  mode: string;
  is_baseline: boolean;
  counts: Record<Verdict, Counts>;
  median_abs_z: Record<string, number | null>;
  vs_baseline: VsBaseline[] | null;
}

export interface Board {
  baseline: string;
  n_cases: number;
  generators: Generator[];
}

export interface Spectrum {
  freq: number[];
  real: number[];
  synthetic: number[];
  ref_p5: number[];
  ref_p95: number[];
  nyquist: number;
}

export interface Glcm {
  levels: number;
  real: number[][];
  synthetic: number[][];
  tones: {
    real: { zero_pct: number; top_pct: number };
    synthetic: { zero_pct: number; top_pct: number };
  };
}

export interface NexWindow {
  row: number;
  col: number;
  value: number | null;
}

export interface Nex {
  real: NexWindow[];
  synthetic: NexWindow[];
  tile: number;
  value_real: number | null;
  value_synthetic: number | null;
  p5: number | null;
  p95: number | null;
}

export interface WaveletBands {
  bands: {
    level: number;
    band: string;
    real: number | null;
    synthetic: number | null;
    log2_ratio: number | null;
  }[];
  type: string;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

type Params = Record<string, string | number | boolean | undefined>;

function query(params?: Params): string {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

async function request<T>(method: string, path: string, params?: Params, body?: unknown): Promise<T> {
  const init: RequestInit = { method };
  if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }
  const response = await fetch(`${path}${query(params)}`, init);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === "string") detail = payload.detail;
    } catch {
      // corpo que não é JSON: fica com o texto de status
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export function get<T>(path: string, params?: Params): Promise<T> {
  return request<T>("GET", path, params);
}

export function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>("POST", path, undefined, body);
}

export function del<T>(path: string): Promise<T> {
  return request<T>("DELETE", path);
}

const enc = encodeURIComponent;

export function imageUrl(
  version: string,
  caseId: string,
  kind: "real" | "synthetic" | "diff" | "contour",
  size?: number,
): string {
  return `/api/image/${enc(version)}/${enc(caseId)}/${kind}.png${query(size ? { size } : undefined)}`;
}

export function toolPath(version: string, caseId: string, tool: "spectrum" | "glcm" | "nex" | "wavelet"): string {
  return `/api/tools/${enc(version)}/${enc(caseId)}/${tool}`;
}

export function figureUrl(caseId: string, technique: string): string {
  return `/api/figure/${enc(caseId)}/technique/${enc(technique)}.png`;
}

export function mapUrl(caseId: string, layer: string, compared: boolean): string {
  return `/api/figure/${enc(caseId)}/map/${enc(layer)}.png${query({ compared: compared ? 1 : 0 })}`;
}
