// Bundles de fixtures tipados pelo contrato: real.json sai das rotas do contrato (workbench/web/scripts/make_real_fixture.py);
// stress.json sai de docs/planning/mockups-v3/bundle_stress.py.
import type {
  Board,
  DetectedRun,
  Experiments,
  InspectorPayload,
  Item,
  Runs,
  Schema,
  Transition,
  VersionInfo,
} from "../contract/types";
import real from "./real.json";
import stress from "./stress.json";

export interface Bundle {
  schema: Schema;
  baseline: string;
  current: string;
  items: Record<string, Item[]>;
  focus: string;
  compare_items: string[];
  inspect: Record<string, InspectorPayload>;
  compare_inspect: { inspector: string; payload: InspectorPayload };
  board: Board;
  transitions: Record<string, Transition[]>;
  runs: Runs | null;
  experiments: Experiments | null;
  versions: VersionInfo[];
  detected: DetectedRun[];
}

export const realBundle = real as unknown as Bundle;
export const stressBundle = stress as unknown as Bundle;
export const bundles: Record<"real" | "stress", Bundle> = { real: realBundle, stress: stressBundle };
