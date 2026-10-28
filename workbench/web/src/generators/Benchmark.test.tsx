// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import type { Schema } from "../contract/types";
import { realBundle, stressBundle, type Bundle } from "../fixtures";
import type { Route } from "../route";
import { clearContractCache } from "../contract/client";
import { Benchmark, GeneratorBenchmark, type BenchmarkProps } from "./Benchmark";
import { defaultCurrent, transitionSummary, type BenchBoard } from "./bench";

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
});

/** The fixture board in the API shape: labels from the versions list; baseline row without comparison. */
function apiBoard(b: Bundle): BenchBoard {
  const base = b.schema.dataset.default_baseline;
  return {
    ...b.board,
    versions: b.board.versions.map(v => ({
      ...v,
      label: b.versions.find(x => x.name === v.name)?.label ?? v.name,
      vs_baseline: v.name === base ? null : v.vs_baseline,
      cohort: v.name === base ? [] : v.cohort,
    })),
  };
}

function props(b: Bundle, over: Partial<BenchmarkProps> = {}): BenchmarkProps {
  const board = apiBoard(b);
  const baseline = b.schema.dataset.default_baseline;
  const axis = b.schema.axes[0].key;
  const items = b.items[b.current] ?? [];
  return {
    schema: b.schema,
    board,
    baseline,
    current: defaultCurrent(board.versions, baseline, b.current),
    axis,
    transitions: b.transitions[axis] ?? [],
    items: Object.fromEntries(items.map(i => [i.id, i])),
    runKeys: new Set((b.runs?.runs ?? []).map(r => r.key)),
    onRoute: vi.fn(),
    ...over,
  };
}

async function render(p: BenchmarkProps) {
  await act(async () => root.render(<Benchmark {...p} />));
  return p;
}

const headCells = () => Array.from(host.querySelectorAll(".gb-thead > div")).map(d => d.textContent);
const button = (text: string) => Array.from(host.querySelectorAll("button")).find(b => b.textContent === text);
const click = async (el: Element | undefined | null) => {
  expect(el).toBeTruthy();
  await act(async () => (el as HTMLElement).click());
};

test("stress (2 axes): two axis columns with chips, no cohort row, no dataset switch, no Notebook tab", async () => {
  const p = await render(props(stressBundle));
  const axes = stressBundle.schema.axes;
  expect(axes).toHaveLength(2);
  expect(headCells()).toEqual(["Generator", ...axes.map(a => a.label), "vs baseline"]);
  expect(host.querySelectorAll(".gb-cohort")).toHaveLength(0);
  expect(host.querySelectorAll(".gb-sbar")).toHaveLength(0);
  expect(host.querySelectorAll(".gb-cnt").length).toBeGreaterThan(0);
  expect(host.querySelector('[aria-label="Dataset"]')).toBeNull();
  const tabs = Array.from(host.querySelectorAll('[aria-label="Generators pages"] button')).map(b => b.textContent);
  expect(tabs).toEqual(["Benchmark", "Optimizers"]);
  // versions shown only by label
  expect(host.querySelector(".gb-table")?.textContent).not.toContain(p.board.versions[1].name);
});

test("five synthetic axes: stacked status bars instead of chips", async () => {
  const base = stressBundle.schema;
  const axes = ["a1", "a2", "a3", "a4", "a5"].map(k => ({ key: k, label: k.toUpperCase() }));
  const schema: Schema = { ...base, axes };
  const board = apiBoard(stressBundle);
  const counts = Object.values(board.versions[0].counts)[0];
  const wide = {
    ...board,
    versions: board.versions.map(v => ({ ...v, counts: Object.fromEntries(axes.map(a => [a.key, counts])) })),
  };
  await render(props(stressBundle, { schema, board: wide, axis: "a1", transitions: [] }));
  expect(headCells()).toEqual(["Generator", ...axes.map(a => a.label), "vs baseline"]);
  expect(host.querySelectorAll(".gb-sbar")).toHaveLength(axes.length * wide.versions.length);
  expect(host.querySelectorAll(".gb-cnt")).toHaveLength(0);
});

test("real: cohort rows first in the indicators card, then clear differences", async () => {
  const p = await render(props(realBundle));
  const cur = p.board.versions.find(v => v.name === p.current)!;
  const rows = Array.from(host.querySelectorAll(".gb-irows .gb-irow"));
  const nCohort = cur.cohort.length;
  const clear = (cur.vs_baseline ?? []).filter(v => v.result === "improved" || v.result === "worse");
  expect(rows).toHaveLength(nCohort + clear.length);
  rows.slice(0, nCohort).forEach((r, i) => {
    expect(r.classList.contains("gb-cohort")).toBe(true);
    const test = realBundle.schema.cohort_tests.find(t => t.key === cur.cohort[i].test)!;
    expect(r.textContent).toContain(test.label);
    expect(r.textContent).toContain(cur.cohort[i].result.label);
  });
  rows.slice(nCohort).forEach((r, i) => {
    const ind = realBundle.schema.indicators.find(x => x.key === clear[i].indicator)!;
    expect(r.textContent).toContain(ind.label);
  });
  // dataset switch with descriptive labels (more than one dataset)
  const ds = host.querySelector('[aria-label="Dataset"]');
  expect(Array.from(ds!.querySelectorAll("button")).map(b => b.textContent)).toEqual(
    realBundle.schema.datasets.map(d => d.label),
  );
});

test("real: provenance link only when the run exists; it opens Optimizers", async () => {
  const p = await render(props(realBundle));
  const withRun = p.board.versions.filter(v => v.provenance && p.runKeys.has(v.provenance.run));
  const links = Array.from(host.querySelectorAll("button.gb-otag"));
  expect(links).toHaveLength(withRun.length);
  await click(links[0]);
  expect(p.onRoute).toHaveBeenCalledWith(expect.objectContaining({ tab: "runs", run: withRun[0].provenance!.run }));

  await render(props(realBundle, { runKeys: new Set() }));
  expect(host.querySelectorAll("button.gb-otag")).toHaveLength(0);
});

test("real: better/worse pills per version and baseline tag", async () => {
  const p = await render(props(realBundle));
  const rows = Array.from(host.querySelectorAll(".gb-trow"));
  expect(rows).toHaveLength(p.board.versions.length);
  expect(rows[0].textContent).toContain(p.board.versions.find(v => v.name === p.baseline)!.label);
  expect(rows[0].querySelector(".gb-base")).toBeTruthy();
  const cur = p.board.versions.find(v => v.name === p.current)!;
  const better = cur.vs_baseline!.filter(v => v.result === "improved").length;
  const worse = cur.vs_baseline!.filter(v => v.result === "worse").length;
  const row = rows.find(r => r.classList.contains("on"))!;
  expect(row.textContent).toContain(`${better} better`);
  expect(row.textContent).toContain(`${worse} worse`);
});

test("real: clicking a version row selects it; baseline select changes the baseline", async () => {
  const p = await render(props(realBundle));
  const ref = p.board.versions.find(v => v.is_reference)!;
  const refRow = Array.from(host.querySelectorAll(".gb-trow")).find(r => r.textContent?.includes(ref.label!))!;
  await click(refRow);
  expect(p.onRoute).toHaveBeenCalledWith({ version: ref.name });

  const select = host.querySelector<HTMLSelectElement>('select[aria-label="Baseline"]')!;
  expect(select.value).toBe(p.baseline);
  expect(Array.from(select.options).map(o => o.textContent)).toEqual(p.board.versions.map(v => v.label));
  await act(async () => {
    select.value = ref.name;
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
  expect(p.onRoute).toHaveBeenCalledWith({ baseline: ref.name });
});

test("real: transitions summary, worst first list, filters and row click opening the item", async () => {
  const axis = "noise";
  const t = realBundle.transitions[axis];
  const p = await render(props(realBundle, { axis, transitions: t }));
  const s = transitionSummary(t);
  const line = host.querySelector(".gb-tsum")!.textContent!;
  expect(line).toContain(`${s.worsened} worsened`);
  expect(line).toContain(`${s.improved} improved`);
  expect(line).toContain(`${s.becameApproved} became approved`);
  expect(line).toContain(`of ${p.board.n_items}`);

  const rows = () => Array.from(host.querySelectorAll(".gb-xr"));
  expect(rows()).toHaveLength(s.worsened + s.improved);
  expect(rows()[0].querySelector(".gb-chg")?.textContent).toContain("Worsened");
  expect(rows()[rows().length - 1].querySelector(".gb-chg")?.textContent).toContain("Improved");
  // item labels, never ids
  const first = t.find(x => x.change === "worsened")!;
  expect(host.querySelector(".gb-xtable")?.textContent).not.toContain(first.id);

  await click(button("Improved"));
  expect(rows()).toHaveLength(s.improved);
  await click(button("Became approved"));
  expect(rows()).toHaveLength(s.becameApproved);
  await click(button("Worsened"));
  expect(rows()).toHaveLength(s.worsened);

  await click(rows()[0]);
  expect(p.onRoute).toHaveBeenCalledWith(
    expect.objectContaining({ section: "dataset", tab: "item", version: p.current }),
  );

  // axis seg lives in the transitions card
  const seg = host.querySelector('[aria-label="Transition axis"]')!;
  await click(Array.from(seg.querySelectorAll("button")).find(b => b.textContent === realBundle.schema.axes[0].label));
  expect(p.onRoute).toHaveBeenCalledWith({ axis: realBundle.schema.axes[0].key });
});

test("real: All indicators shows the per-version score table", async () => {
  const p = await render(props(realBundle));
  expect(host.querySelector(".gb-scores")).toBeNull();
  await click(button("All indicators"));
  const table = host.querySelector(".gb-scores")!;
  expect(table).toBeTruthy();
  const head = Array.from(table.querySelectorAll("thead th")).map(th => th.textContent);
  for (const v of p.board.versions) expect(head).toContain(v.label);
  expect(table.querySelectorAll("tbody tr")).toHaveLength(realBundle.schema.indicators.length);
});

test("no current version: indicators and transitions show empty states", async () => {
  const b = props(realBundle);
  const only = { ...b.board, versions: b.board.versions.filter(v => v.name === b.baseline) };
  await render({ ...b, board: only, current: undefined, transitions: [] });
  expect(host.querySelectorAll(".gb-trow")).toHaveLength(1);
  expect(host.textContent).toContain("No other version to compare");
});

test("GeneratorBenchmark: unknown route baseline falls back to the default; loads board, transitions, items and runs", async () => {
  clearContractCache();
  const b = realBundle;
  const key = b.schema.dataset.key;
  const base = b.schema.dataset.default_baseline;
  const board = apiBoard(b);
  const current = defaultCurrent(board.versions, base, undefined)!;
  const axis = b.schema.axes[0].key;
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      calls.push(url);
      const path = url.split("?")[0];
      const body =
        path === "/api/v2/versions"
          ? b.versions
          : path === "/api/v2/board"
            ? board
            : path === "/api/v2/transitions"
              ? b.transitions[axis]
              : path === "/api/items"
                ? { version: current, items: b.items[current] }
                : path === "/api/runs"
                  ? b.runs
                  : null;
      if (body === null) throw new Error(`unexpected ${url}`);
      return { ok: true, status: 200, statusText: "OK", json: async () => body };
    }),
  );
  try {
    const route: Route = { section: "generators", tab: "bench", baseline: "nope" };
    await act(async () => root.render(<GeneratorBenchmark schema={b.schema} route={route} onRoute={vi.fn()} />));
    for (let i = 0; i < 6; i++) await act(async () => new Promise(r => setTimeout(r, 0)));
    expect(calls).toContain(`/api/v2/board?dataset=${key}&baseline=${encodeURIComponent(base)}`);
    expect(calls.some(c => c.startsWith("/api/v2/transitions") && c.includes(`after=${encodeURIComponent(current)}`))).toBe(true);
    expect(calls.some(c => c.startsWith("/api/runs"))).toBe(b.schema.addons.optimizers);
    expect(host.querySelector<HTMLSelectElement>('select[aria-label="Baseline"]')!.value).toBe(base);
    const s = transitionSummary(b.transitions[axis]);
    expect(host.querySelectorAll(".gb-xr")).toHaveLength(s.worsened + s.improved);
  } finally {
    vi.unstubAllGlobals();
  }
});
