// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { orderItems } from "../contract/format";
import type { Item, MetricDesc, Schema } from "../contract/types";
import { realBundle, stressBundle, type Bundle } from "../fixtures";
import { CohortCharts } from "./CohortCharts";
import { alignTo, cohortSeries, factDistribution, matrixRows, scatterSeries, tableOrder } from "./cohort";
import { ItemTable } from "./ItemTable";
import { axisTechniques } from "./strip";
import { VerdictMatrix } from "./VerdictMatrix";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const metric = (b: Bundle, key: string): MetricDesc => {
  const m = b.schema.metrics.find(x => x.key === key);
  if (!m) throw new Error(`metric ${key} missing from fixture`);
  return m;
};
const current = (b: Bundle) => b.items[b.current];
const finite = (x: number | null | undefined): x is number => typeof x === "number" && Number.isFinite(x);

describe("cohortSeries", () => {
  test("real nps_air: bands 0–0.5 approved, 0.5–2 review, >2 rejected", () => {
    const m = metric(realBundle, "nps_air");
    const s = cohortSeries(current(realBundle), m, realBundle.schema);
    expect(s.bands.slice(0, 2)).toEqual([
      { from: 0, to: m.limits!.review, status: "approved" },
      { from: m.limits!.review, to: m.limits!.reject, status: "review" },
    ]);
    expect(s.bands[2]).toEqual({ from: m.limits!.reject, to: s.domain[1], status: "rejected" });
    expect(s.bands).toHaveLength(3);
    expect(s.domain[1]).toBeGreaterThan(m.limits!.reject!);
  });

  test("abs_z bands are symmetric around zero", () => {
    const m = metric(realBundle, "glcm_contrast");
    const s = cohortSeries(current(realBundle), m, realBundle.schema);
    const [lo, hi] = s.domain;
    const R = m.limits!.review!, J = m.limits!.reject!;
    expect(s.bands).toEqual([
      { from: lo, to: -J, status: "rejected" },
      { from: -J, to: -R, status: "review" },
      { from: -R, to: R, status: "approved" },
      { from: R, to: J, status: "review" },
      { from: J, to: hi, status: "rejected" },
    ]);
  });

  test("a metric with unread items skips their points and keeps every other index", () => {
    const items = current(realBundle);
    const m = metric(realBundle, "nex");
    const s = cohortSeries(items, m, realBundle.schema);
    const unread = items.filter(it => !finite(it.metrics.nex?.z));
    expect(unread.length).toBeGreaterThan(0);
    expect(s.points.length).toBe(items.length - unread.length);
    expect(s.points.length).toBeLessThan(items.length);
    for (const p of s.points) {
      expect(items[p.index].id).toBe(p.id);
      expect(p.y).toBe(items[p.index].metrics.nex.z);
    }
    expect(s.points.map(p => p.index)).toEqual(
      items.map((it, i) => (finite(it.metrics.nex?.z) ? i : -1)).filter(i => i >= 0),
    );
  });

  test("with compareItems the domain is shared and covers both versions", () => {
    const a = realBundle.items[realBundle.baseline];
    const b = current(realBundle);
    for (const m of realBundle.schema.metrics) {
      const sa = cohortSeries(a, m, realBundle.schema, b);
      const sb = cohortSeries(b, m, realBundle.schema, a);
      expect(sa.domain).toEqual(sb.domain);
      const own = cohortSeries(a, m, realBundle.schema);
      expect(sa.domain[0]).toBeLessThanOrEqual(own.domain[0]);
      expect(sa.domain[1]).toBeGreaterThanOrEqual(own.domain[1]);
      for (const p of [...sa.points, ...sb.points]) {
        for (const v of [p.y, p.lo, p.hi].filter(finite)) {
          expect(v).toBeGreaterThanOrEqual(sa.domain[0]);
          expect(v).toBeLessThanOrEqual(sa.domain[1]);
        }
      }
    }
  });
});

describe("scatterSeries", () => {
  test("only items with both readings, scale max shared with the compare version", () => {
    const items = current(realBundle);
    const m = metric(realBundle, "nps_quantity");
    const s = scatterSeries(items, m);
    const both = items.filter(it => finite(it.metrics[m.key]?.real) && finite(it.metrics[m.key]?.synthetic));
    expect(s.points).toHaveLength(both.length);
    const other = realBundle.items[realBundle.baseline];
    const shared = scatterSeries(items, m, other);
    expect(shared.max).toBeGreaterThanOrEqual(s.max);
    expect(scatterSeries(items, metric(realBundle, "sat31")).points).toHaveLength(0);
  });
});

describe("matrixRows and alignment", () => {
  test("verdict row then one row per technique of the axis; cells follow item order", () => {
    const b = realBundle;
    const items = orderItems(current(b), "noise", b.schema);
    const rows = matrixRows(items, "noise", b.schema);
    expect(rows.map(r => r.key)).toEqual(["verdict", ...axisTechniques(items, "noise", b.schema).map(t => t.key)]);
    expect(rows[0].cells.map(c => c.id)).toEqual(items.map(i => i.id));
    for (const c of rows.flatMap(r => r.cells)) {
      expect(c.title).not.toMatch(/null|undefined/);
    }
  });

  test("alignTo keeps the first version's order for the second", () => {
    const a = orderItems(current(realBundle), "texture", realBundle.schema);
    const b = realBundle.items[realBundle.baseline];
    expect(alignTo(a, b).map(i => i.id)).toEqual(a.map(i => i.id).filter(id => b.some(x => x.id === id)));
  });

  test("tableOrder defaults to severity then spread (orderItems)", () => {
    const s: Schema = stressBundle.schema;
    const items = current(stressBundle);
    const axis = s.axes[0].key;
    expect(tableOrder(items, axis, s, null).map(i => i.id)).toEqual(orderItems(items, axis, s).map(i => i.id));
  });
});

// ------------------------------------------------------------------ components

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

const draw = (el: Parameters<typeof root.render>[0]) => act(async () => root.render(el));

test("Matrix on stress renders 2 + techniques rows per axis (header, verdict, techniques)", async () => {
  const b = stressBundle;
  for (const axis of b.schema.axes) {
    const items = orderItems(current(b), axis.key, b.schema);
    await draw(createElement(VerdictMatrix, { schema: b.schema, axis: axis.key, items, onOpen: vi.fn() }));
    const n = axisTechniques(items, axis.key, b.schema).length;
    expect(host.querySelectorAll("table.vmx tr")).toHaveLength(2 + n);
  }
});

test("Matrix cell click opens the item; with a compare version two matrices share the order", async () => {
  const b = realBundle;
  const onOpen = vi.fn();
  const items = orderItems(current(b), "texture", b.schema);
  const other = b.items[b.baseline];
  await draw(
    createElement(VerdictMatrix, {
      schema: b.schema,
      axis: "texture",
      items,
      onOpen,
      compare: { label: "baseline", items: other },
    }),
  );
  const tables = host.querySelectorAll("table.vmx");
  expect(tables).toHaveLength(2);
  const ids = (t: Element) => Array.from(t.querySelectorAll("tr.vmx-verdict button")).map(x => (x as HTMLElement).dataset.id);
  expect(ids(tables[1])).toEqual(ids(tables[0]).filter(id => other.some(x => x.id === id)));
  await act(async () => (tables[0].querySelector("tr.vmx-verdict button") as HTMLButtonElement).click());
  expect(onOpen).toHaveBeenCalledWith(items[0].id);
});

test("Charts: one strip chart per axis metric, null points skipped, click opens; scatter only with both readings", async () => {
  const b = realBundle;
  const onOpen = vi.fn();
  const items = orderItems(current(b), "noise", b.schema);
  await draw(createElement(CohortCharts, { schema: b.schema, axis: "noise", items, onOpen }));
  const metrics = b.schema.metrics.filter(m => m.axis === "noise");
  expect(host.querySelectorAll("svg.cohort-strip")).toHaveLength(metrics.length);
  const scatterable = metrics.filter(m => items.some(it => finite(it.metrics[m.key]?.real) && finite(it.metrics[m.key]?.synthetic)));
  expect(host.querySelectorAll("svg.cohort-scatter")).toHaveLength(scatterable.length);
  const first = host.querySelector("svg.cohort-strip")!;
  const m0 = metrics[0];
  expect(first.querySelectorAll("circle.pt")).toHaveLength(cohortSeries(items, m0, b.schema).points.length);
  const pt = first.querySelector<SVGCircleElement>("circle.pt")!;
  await act(async () => pt.dispatchEvent(new MouseEvent("click", { bubbles: true })));
  expect(onOpen).toHaveBeenCalledWith(pt.dataset.id);
});

test("Table: one row per item in severity order, metric text and row click", async () => {
  const b = stressBundle;
  const onOpen = vi.fn();
  const axis = b.schema.axes[0].key;
  const items = current(b);
  await draw(createElement(ItemTable, { schema: b.schema, axis, items, onOpen }));
  const rows = Array.from(host.querySelectorAll<HTMLTableRowElement>("table.itab tbody tr"));
  expect(rows.map(r => r.dataset.id)).toEqual(orderItems(items, axis, b.schema).map(i => i.id));
  const heads = Array.from(host.querySelectorAll("table.itab thead th")).map(t => t.textContent);
  for (const m of b.schema.metrics.filter(x => x.axis === axis)) expect(heads).toContain(m.label);
  await act(async () => rows[3].click());
  expect(onOpen).toHaveBeenCalledWith(rows[3].dataset.id);
  // sort by name and back
  const nameHead = Array.from(host.querySelectorAll<HTMLButtonElement>("table.itab thead th button")).find(
    x => x.textContent?.startsWith(b.schema.dataset.item.singular.slice(0, 1).toUpperCase()),
  )!;
  await act(async () => nameHead.click());
  const byName = Array.from(host.querySelectorAll<HTMLTableRowElement>("table.itab tbody tr")).map(r => r.dataset.id);
  expect(byName).toEqual([...items].sort((x: Item, y: Item) => (x.label < y.label ? -1 : x.label > y.label ? 1 : 0)).map(i => i.id));
});

describe("factDistribution (parity #33)", () => {
  // recontagem direta dos fatos do fixture: valor -> quantidade
  const recount = (items: Item[], label: string) => {
    const counts = new Map<string, number>();
    for (const it of items) {
      const value = it.facts.find(f => f.label === label)?.value;
      if (value !== undefined) counts.set(value, (counts.get(value) ?? 0) + 1);
    }
    return counts;
  };

  test("real: one line per categorical fact, counts sum to the items, most frequent first", () => {
    const items = current(realBundle);
    const dist = factDistribution(items);
    expect(dist.length).toBeGreaterThan(0);
    for (const d of dist) {
      const counts = recount(items, d.label);
      expect(new Map(d.values.map(v => [v.value, v.count]))).toEqual(counts);
      expect(d.values.reduce((n, v) => n + v.count, 0)).toBe(items.filter(it => it.facts.some(f => f.label === d.label)).length);
      const ns = d.values.map(v => v.count);
      expect(ns).toEqual([...ns].sort((a, c) => c - a));
    }
  });

  test("numeric or all-distinct facts are not categorical", () => {
    // stress: Seed is a different number per image
    expect(factDistribution(current(stressBundle))).toEqual([]);
    const mk = (id: string, facts: { label: string; value: string }[]) => ({ ...current(stressBundle)[0], id, facts });
    const items = [
      mk("a", [{ label: "Kind", value: "x" }, { label: "Count", value: "3" }, { label: "Tag", value: "p" }]),
      mk("b", [{ label: "Kind", value: "x" }, { label: "Count", value: "3" }, { label: "Tag", value: "q" }]),
      mk("c", [{ label: "Kind", value: "y" }, { label: "Count", value: "4" }, { label: "Tag", value: "r" }]),
    ];
    expect(factDistribution(items)).toEqual([{ label: "Kind", values: [{ value: "x", count: 2 }, { value: "y", count: 1 }] }]);
  });

  test("Table footer prints the distribution of each categorical fact", async () => {
    const b = realBundle;
    const items = current(b);
    await draw(createElement(ItemTable, { schema: b.schema, axis: b.schema.axes[0].key, items, onOpen: vi.fn() }));
    const lines = Array.from(host.querySelectorAll(".itab-dist li")).map(li => li.textContent);
    expect(lines).toEqual(
      factDistribution(items).map(d => `${d.label}: ${d.values.map(v => `${v.value} ${v.count}`).join(" · ")}`),
    );
  });
});
