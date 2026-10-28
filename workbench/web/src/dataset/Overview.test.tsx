// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { realBundle, stressBundle, type Bundle } from "../fixtures";
import type { Route } from "../route";
import { DatasetOverview, Overview } from "./Overview";

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

async function render(b: Bundle, route: Partial<Route> = {}, onRoute = vi.fn()) {
  const full: Route = { section: "dataset", tab: "overview", ...route };
  await act(async () =>
    root.render(
      <Overview
        schema={b.schema}
        items={b.items[b.current]}
        version={b.current}
        versions={b.versions}
        route={full}
        onRoute={onRoute}
      />,
    ),
  );
  return onRoute;
}

const tiles = () => Array.from(host.querySelectorAll<HTMLButtonElement>("button.ov-tile"));
const button = (text: string) => Array.from(host.querySelectorAll("button")).find(b => b.textContent === text);

test("stress fixture: flat grid, Images heading, no dataset switch", async () => {
  await render(stressBundle);
  expect(host.querySelector("h1")?.textContent).toBe("Images");
  expect(host.querySelectorAll(".ov-group")).toHaveLength(0);
  expect(tiles()).toHaveLength(stressBundle.items[stressBundle.current].length);
  expect(host.querySelector('[aria-label="Dataset"]')).toBeNull();
  // histogram above 60 items
  expect(host.querySelectorAll(".ov-bars i.stk")).toHaveLength(30);
});

test("real fixture: groups by group_by, dataset switch with descriptive labels", async () => {
  await render(realBundle);
  const items = realBundle.items[realBundle.current];
  expect(host.querySelector("h1")?.textContent).toBe("Slices");
  const groups = new Set(items.map(i => i.group));
  expect(host.querySelectorAll(".ov-group")).toHaveLength(groups.size);
  const sw = host.querySelector('[aria-label="Dataset"]');
  expect(sw).not.toBeNull();
  expect(Array.from(sw!.querySelectorAll("button")).map(b => b.textContent)).toEqual(
    realBundle.schema.datasets.map(d => d.label),
  );
  expect(host.querySelector(".sub")?.textContent).toBe(`${items.length} slices · ${groups.size} patients`);
  expect(host.querySelector(".eyebrow")?.textContent).toBe(`Dataset · ${realBundle.schema.dataset.mode_label}`);
  // one bar per item up to 60
  expect(host.querySelectorAll(".ov-bars i")).toHaveLength(items.length);
});

test("version chip lists version labels, never folder names", async () => {
  await render(realBundle);
  const select = host.querySelector<HTMLSelectElement>('select[aria-label="Version"]')!;
  expect(Array.from(select.options).map(o => o.textContent)).toEqual(realBundle.versions.map(v => v.label));
});

test("tile click opens the item; shift/cmd-click selects up to 4 and Compare opens them", async () => {
  const onRoute = await render(realBundle);
  const t = tiles();
  await act(async () => t[0].click());
  expect(onRoute).toHaveBeenLastCalledWith(expect.objectContaining({ tab: "item", item: t[0].dataset.id }));

  onRoute.mockClear();
  for (const tile of t.slice(0, 5)) {
    await act(async () => tile.dispatchEvent(new MouseEvent("click", { bubbles: true, shiftKey: true })));
  }
  expect(onRoute).not.toHaveBeenCalled();
  expect(host.querySelectorAll("button.ov-tile.selected")).toHaveLength(4);
  const compare = button("Compare 4");
  expect(compare).toBeDefined();
  await act(async () => compare!.click());
  expect(onRoute).toHaveBeenLastCalledWith(
    expect.objectContaining({ tab: "compare", items: t.slice(0, 4).map(x => x.dataset.id) }),
  );
});

test("status filter narrows the grid; search matches labels", async () => {
  await render(stressBundle);
  const items = stressBundle.items[stressBundle.current];
  const axis = host.querySelector<HTMLButtonElement>('[aria-label="Axis"] button[aria-pressed="true"]')!;
  const axisKey = stressBundle.schema.axes.find(a => a.label === axis.textContent)!.key;
  const select = host.querySelector<HTMLSelectElement>('select[aria-label="Status"]')!;
  await act(async () => {
    select.value = "rejected";
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
  expect(tiles()).toHaveLength(items.filter(i => i.verdicts[axisKey] === "rejected").length);

  await act(async () => {
    select.value = "all";
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
  const input = host.querySelector<HTMLInputElement>('input[type="search"]')!;
  const target = items[7];
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
  await act(async () => {
    setter.call(input, target.label);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  expect(tiles().map(x => x.dataset.id)).toContain(target.id);
  expect(tiles().length).toBeLessThan(items.length);
});

test("How to read lists every metric with its limits", async () => {
  await render(stressBundle);
  const rows = host.querySelectorAll(".how .lrow:not(.lh)");
  expect(rows).toHaveLength(stressBundle.schema.metrics.length);
});

test("DatasetOverview loads versions, opens the newest non-reference version and shows its label", async () => {
  const b = realBundle;
  const key = b.schema.dataset.key;
  const calls: string[] = [];
  const latest = b.versions.filter(v => !v.is_reference).slice(-1)[0];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      calls.push(url);
      const body = url.startsWith("/api/v2/versions")
        ? b.versions
        : url.startsWith("/api/items")
          ? { version: latest.name, items: b.items[latest.name] }
          : null;
      if (body === null) throw new Error(`unexpected ${url}`);
      return { ok: true, status: 200, statusText: "OK", json: async () => body };
    }),
  );
  try {
    await act(async () =>
      root.render(<DatasetOverview schema={b.schema} route={{ section: "dataset", tab: "overview" }} onRoute={vi.fn()} />),
    );
    for (let i = 0; i < 4; i++) await act(async () => new Promise(r => setTimeout(r, 0)));
    expect(calls).toContain(`/api/v2/versions?dataset=${key}`);
    expect(calls).toContain(`/api/items?dataset=${key}&version=${encodeURIComponent(latest.name)}`);
    const select = host.querySelector<HTMLSelectElement>('select[aria-label="Version"]')!;
    expect(select.selectedOptions[0].textContent).toBe(latest.label);
    expect(tiles()).toHaveLength(b.items[latest.name].length);
  } finally {
    vi.unstubAllGlobals();
  }
});

test("view seg Grid · Charts · Matrix · Table writes the mode to the route", async () => {
  const onRoute = await render(realBundle);
  const seg = host.querySelector('[aria-label="View"]')!;
  expect(Array.from(seg.querySelectorAll("button")).map(b => b.textContent)).toEqual(["Grid", "Charts", "Matrix", "Table"]);
  expect(seg.querySelector('[aria-pressed="true"]')?.textContent).toBe("Grid");
  await act(async () => Array.from(seg.querySelectorAll("button")).find(b => b.textContent === "Matrix")!.click());
  expect(onRoute).toHaveBeenLastCalledWith({ view: "matrix" });
});

test("route view picks the mode: table rows follow the visible items, charts and matrix replace the grid", async () => {
  const b = stressBundle;
  await render(b, { view: "table" });
  expect(tiles()).toHaveLength(0);
  expect(host.querySelectorAll("table.itab tbody tr")).toHaveLength(b.items[b.current].length);
  await render(b, { view: "matrix" });
  expect(host.querySelectorAll("table.vmx")).toHaveLength(1);
  await render(b, { view: "charts" });
  expect(host.querySelectorAll("svg.cohort-strip").length).toBeGreaterThan(0);
});

test("compare with lists the other versions by label, only in charts and matrix", async () => {
  const b = realBundle;
  await render(b, { view: "grid" });
  expect(host.querySelector('select[aria-label="Compare with"]')).toBeNull();
  await render(b, { view: "matrix" });
  const select = host.querySelector<HTMLSelectElement>('select[aria-label="Compare with"]')!;
  expect(Array.from(select.options).map(o => o.textContent)).toEqual([
    "No comparison",
    ...b.versions.filter(v => v.name !== b.current).map(v => v.label),
  ]);
});

test("compare version items load from /api/items and stack a second matrix", async () => {
  const b = realBundle;
  const other = b.versions.find(v => v.name === b.baseline)!;
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      calls.push(url);
      return { ok: true, status: 200, statusText: "OK", json: async () => ({ version: other.name, items: b.items[other.name] }) };
    }),
  );
  try {
    await render(b, { view: "matrix" });
    const select = host.querySelector<HTMLSelectElement>('select[aria-label="Compare with"]')!;
    await act(async () => {
      select.value = other.name;
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    for (let i = 0; i < 4; i++) await act(async () => new Promise(r => setTimeout(r, 0)));
    expect(calls).toContain(`/api/items?dataset=${b.schema.dataset.key}&version=${encodeURIComponent(other.name)}`);
    const tables = host.querySelectorAll("table.vmx");
    expect(tables).toHaveLength(2);
    expect(host.textContent).toContain(other.label);
  } finally {
    vi.unstubAllGlobals();
  }
});
