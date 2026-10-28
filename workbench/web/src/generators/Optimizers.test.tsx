// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import type { Runs, Schema } from "../contract/types";
import { clearContractCache } from "../contract/client";
import { realBundle, stressBundle } from "../fixtures";
import type { Route } from "../route";
import { GeneratorOptimizers, Optimizers, type OptimizersProps } from "./Optimizers";
import { rankRuns } from "./runs";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;

beforeEach(() => {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

function props(schema: Schema, runs: Runs, over: Partial<OptimizersProps> = {}): OptimizersProps {
  return { schema, runs, run: undefined, onRoute: vi.fn(), ...over };
}

async function render(p: OptimizersProps) {
  await act(async () => root.render(<Optimizers {...p} />));
}

const rowNames = () => Array.from(host.querySelectorAll(".opt-row .opt-name")).map(n => n.textContent);
const stepHeads = () => Array.from(host.querySelectorAll(".opt-steps-head > span")).map(s => s.textContent);
const groupOf = (key: string) => host.querySelector<SVGGElement>(`g.opt-run[data-run="${key}"]`);

test("real: GP-BO ranks first; its row title names the best configuration", async () => {
  const runs = realBundle.runs!;
  await render(props(realBundle.schema, runs));
  expect(rowNames()).toEqual(rankRuns(runs.runs).map(r => r.label));
  expect(rowNames()[0]).toBe("GP-BO");
  const best = runs.runs.find(r => r.key === "gp")!;
  const first = host.querySelector<HTMLElement>(".opt-row")!;
  expect(first.getAttribute("title")).toContain(String(best.best_params.steps));
});

test("stress: steps have no Stage and no W / L columns", async () => {
  await render(props(stressBundle.schema, stressBundle.runs!));
  const heads = stepHeads();
  expect(heads).not.toContain("Stage");
  expect(heads).not.toContain("W / L");
  expect(heads[0]).toBe("#");
  expect(heads).toContain("Score");
});

test("real: steps show the Stage and W / L columns and one row per step", async () => {
  const runs = realBundle.runs!;
  await render(props(realBundle.schema, runs));
  const gp = runs.runs.find(r => r.key === "gp")!;
  expect(stepHeads()).toContain("Stage");
  expect(stepHeads()).toContain("W / L");
  expect(host.querySelectorAll(".opt-step")).toHaveLength(gp.steps.length);
});

test("goal rule only when the objective has a goal", async () => {
  await render(props(realBundle.schema, realBundle.runs!));
  expect(host.querySelector(".goal-rule")).not.toBeNull();
  await render(props(stressBundle.schema, stressBundle.runs!));
  expect(stressBundle.runs!.objective.goal).toBeNull();
  expect(host.querySelector(".goal-rule")).toBeNull();
});

test("no runs: empty state", async () => {
  await render(props(realBundle.schema, { ...realBundle.runs!, runs: [] }));
  expect(host.textContent).toContain("No optimizer runs yet");
  expect(host.querySelector(".opt-row")).toBeNull();
});

test("without a selected run the top run is highlighted and no curve is dimmed", async () => {
  const runs = realBundle.runs!;
  await render(props(realBundle.schema, runs));
  const top = rankRuns(runs.runs)[0].key;
  expect(host.querySelector(".opt-row")!.getAttribute("aria-pressed")).toBe("true");
  for (const r of runs.runs) expect(groupOf(r.key)!.style.opacity).toBe("1");
  const gp = runs.runs.find(r => r.key === top)!;
  expect(host.querySelectorAll(".opt-step")).toHaveLength(gp.steps.length);
});

test("clicking a row asks for that run; the selected run keeps its curve and the others dim to 18%", async () => {
  const runs = realBundle.runs!;
  const p = props(realBundle.schema, runs, { run: "nm" });
  await render(p);
  const rows = Array.from(host.querySelectorAll<HTMLElement>(".opt-row"));
  const nm = rows.find(r => r.querySelector(".opt-name")!.textContent === runs.runs.find(x => x.key === "nm")!.label)!;
  await act(async () => nm.click());
  expect(p.onRoute).toHaveBeenCalledWith({ run: "nm" });
  expect(groupOf("nm")!.style.opacity).toBe("1");
  expect(groupOf("gp")!.style.opacity).toBe("0.18");
  expect(nm.getAttribute("aria-pressed")).toBe("true");
  const nmSteps = runs.runs.find(r => r.key === "nm")!.steps.length;
  expect(host.querySelectorAll(".opt-step")).toHaveLength(nmSteps);
});

test("GeneratorOptimizers loads /api/runs and renders the screen; tabs route back to Benchmark", async () => {
  clearContractCache();
  const b = realBundle;
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      calls.push(url);
      if (url.split("?")[0] !== "/api/runs") throw new Error(`unexpected ${url}`);
      return { ok: true, status: 200, statusText: "OK", json: async () => b.runs };
    }),
  );
  const onRoute = vi.fn();
  const route: Route = { section: "generators", tab: "runs" };
  await act(async () => root.render(<GeneratorOptimizers schema={b.schema} route={route} onRoute={onRoute} />));
  for (let i = 0; i < 6; i++) await act(async () => new Promise(r => setTimeout(r, 0)));
  expect(calls.some(c => c.startsWith("/api/runs"))).toBe(true);
  expect(rowNames()[0]).toBe("GP-BO");
  const bench = Array.from(host.querySelectorAll<HTMLButtonElement>('[aria-label="Generators pages"] button')).find(
    x => x.textContent === "Benchmark",
  );
  await act(async () => bench!.click());
  expect(onRoute).toHaveBeenCalledWith({ tab: "bench" });
});
