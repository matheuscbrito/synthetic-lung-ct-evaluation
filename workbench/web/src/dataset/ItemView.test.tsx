// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { clearContractCache } from "../contract/client";
import { metricText, reasonText } from "../contract/format";
import type { Item } from "../contract/types";
import { realBundle, stressBundle, type Bundle } from "../fixtures";
import type { Route } from "../route";
import { DatasetItem, ItemView } from "./ItemView";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;
let calls: string[];

type Reply = { status: number; body: unknown };

// fetch falso: versões, itens e payloads dos inspetores vêm do bundle; `override` responde rotas específicas
function stubFetch(b: Bundle, override: (url: string) => Reply | null = () => null) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      calls.push(url);
      const u = new URL(url, "http://test.invalid");
      const custom = override(url);
      let reply: Reply | null = custom;
      if (!reply && u.pathname === "/api/versions") reply = { status: 200, body: b.versions };
      if (!reply && u.pathname === "/api/items") {
        const version = u.searchParams.get("version")!;
        reply = { status: 200, body: { version, items: b.items[version] } };
      }
      if (!reply && u.pathname.startsWith("/api/inspect/")) {
        const key = decodeURIComponent(u.pathname.slice("/api/inspect/".length));
        reply = { status: 200, body: b.inspect[key] };
      }
      if (!reply) throw new Error(`unexpected ${url}`);
      const { status, body } = reply;
      return { ok: status < 400, status, statusText: "x", json: async () => body };
    }),
  );
}

beforeEach(() => {
  // o cache do contrato é global: cada teste começa sem respostas guardadas
  clearContractCache();
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

const settle = async () => {
  for (let i = 0; i < 5; i++) await act(async () => new Promise(r => setTimeout(r, 0)));
};

const focusOf = (b: Bundle, version = b.current): Item => b.items[version].find(i => i.id === b.focus)!;

async function render(b: Bundle, opts: { items?: Item[]; route?: Partial<Route> } = {}) {
  stubFetch(b);
  const onRoute = vi.fn();
  const route: Route = { section: "dataset", tab: "item", item: b.focus, ...opts.route };
  await act(async () =>
    root.render(
      <ItemView
        schema={b.schema}
        versions={b.versions}
        version={b.current}
        items={opts.items ?? b.items[b.current]}
        compare={b.baseline}
        compareItems={b.items[b.baseline]}
        route={route}
        onRoute={onRoute}
      />,
    ),
  );
  await settle();
  return onRoute;
}

const label = (b: Bundle, name: string) => b.versions.find(v => v.name === name)!.label;

test("stress focus item: one verdict column per axis and one inspector tab per inspector", async () => {
  const b = stressBundle;
  await render(b);
  const cols = host.querySelectorAll(".vhead .vcol");
  expect(cols).toHaveLength(b.schema.axes.length);
  expect(b.schema.axes).toHaveLength(2);
  expect(host.querySelectorAll(".vhead .ui-pill.cur")).toHaveLength(2);
  const tabs = host.querySelectorAll('[aria-label="Inspector"] button');
  expect(Array.from(tabs).map(t => t.textContent)).toEqual(b.schema.inspectors.map(i => i.label));
  expect(tabs).toHaveLength(4);
  // crumbs: version label › item label (no group in this dataset)
  expect(host.querySelector(".crumbs")?.textContent).toContain(label(b, b.current));
  expect(host.querySelector(".crumbs b")?.textContent).toBe(focusOf(b).label);
});

test("verdict pills show previous → current when the compare version differs", async () => {
  const b = stressBundle;
  await render(b);
  const before = focusOf(b, b.baseline);
  const after = focusOf(b);
  const statusLabel = (k: string) => b.schema.statuses.find(s => s.key === k)!.label;
  b.schema.axes.forEach((a, i) => {
    const col = host.querySelectorAll(".vhead .vcol")[i];
    const prev = col.querySelector(".ui-pill.prev");
    if (before.verdicts[a.key] !== after.verdicts[a.key]) {
      expect(prev?.textContent).toBe(statusLabel(before.verdicts[a.key]));
      expect(col.textContent).toContain("→");
    } else {
      expect(prev).toBeNull();
    }
    expect(col.querySelector(".ui-pill.cur")?.textContent).toBe(statusLabel(after.verdicts[a.key]));
  });
  // at least one axis differs in this fixture, so the arrow is exercised
  expect(b.schema.axes.some(a => before.verdicts[a.key] !== after.verdicts[a.key])).toBe(true);
});

test("real focus item: every reason sentence, % of original for nex, compare value in a muted column", async () => {
  const b = realBundle;
  const focus = focusOf(b);
  const nex = focus.metrics.nex;
  // o fixture não traz `pct`; o backend o calcula como sintética ÷ real × 100
  const pct = (100 * nex.synthetic!) / nex.real!;
  const items = b.items[b.current].map(it => (it.id === focus.id ? { ...it, metrics: { ...it.metrics, nex: { ...nex, pct } } } : it));
  await render(b, { items });

  const reasons = Array.from(host.querySelectorAll(".why li")).map(li => li.textContent);
  expect(reasons).toHaveLength(focus.reasons.length);
  expect(focus.reasons).toHaveLength(5);
  const desc = (k: string) => b.schema.metrics.find(m => m.key === k)!;
  expect(reasons).toEqual(
    b.schema.axes.flatMap(a => focus.reasons.filter(r => r.axis === a.key).map(r => reasonText(desc(r.metric), r))),
  );

  const row = host.querySelector<HTMLElement>('.mrow[data-metric="nex"]')!;
  expect(row.querySelector(".pct")?.textContent).toBe(`${Math.round(pct)}% of original`);
  expect(row.querySelector(".cur-val")?.textContent).toBe(metricText(desc("nex"), nex));
  const old = focusOf(b, b.baseline).metrics.nex;
  expect(row.querySelector(".cmp-val")?.textContent).toBe(metricText(desc("nex"), old));
  // only nex carries pct here
  expect(host.querySelectorAll(".mrow .pct")).toHaveLength(1);
  // one metric row per metric, grouped under each axis
  expect(host.querySelectorAll(".mrow[data-metric]")).toHaveLength(b.schema.metrics.length);
  // facts
  const facts = Array.from(host.querySelectorAll(".fact")).map(f => f.textContent);
  expect(facts).toEqual(focus.facts.map(f => `${f.label}${f.value}`));
  // group in the crumbs
  expect(host.querySelector(".crumbs")?.textContent).toContain(`${b.schema.dataset.group_by!.label} ${focus.group}`);
});

test("a reason with a note and no value prints the note", async () => {
  const b = realBundle;
  const focus = focusOf(b);
  const r = { ...focus.reasons[0], value: null, z: null, ci: null, note: "air unavailable" };
  const items = b.items[b.current].map(it => (it.id === focus.id ? { ...it, reasons: [r] } : it));
  await render(b, { items });
  const li = Array.from(host.querySelectorAll(".why li")).map(x => x.textContent);
  expect(li).toHaveLength(1);
  expect(li[0]).toContain("air unavailable");
  expect(li[0]).not.toContain("null");
});

test("triptych: original, compare version and current share the reference window; compare seg swaps the middle pane", async () => {
  const b = realBundle;
  const onRoute = await render(b);
  const panes = host.querySelectorAll(".panes .pane");
  expect(panes).toHaveLength(3);
  const base = (p: Element) => p.querySelector<HTMLImageElement>("img.base")!.getAttribute("src")!;
  const enc = encodeURIComponent(b.focus);
  expect(base(panes[0])).toContain(`/${enc}/real.png`);
  expect(base(panes[1])).toContain(`/api/image/${encodeURIComponent(b.baseline)}/${enc}/synthetic.png`);
  expect(base(panes[2])).toContain(`/api/image/${encodeURIComponent(b.current)}/${enc}/synthetic.png`);
  for (const p of panes) expect(base(p)).toContain("window=reference");
  expect(panes[1].textContent).toContain(label(b, b.baseline));

  // contour overlay toggle
  expect(host.querySelectorAll(".panes img.contour")).toHaveLength(3);
  const toggle = host.querySelector<HTMLInputElement>('input[aria-label="Contour"]')!;
  await act(async () => toggle.click());
  expect(host.querySelectorAll(".panes img.contour")).toHaveLength(0);

  // Compare with: every other version by label
  const seg = host.querySelector('[aria-label="Compare with"]')!;
  const others = b.versions.filter(v => v.name !== b.current);
  expect(Array.from(seg.querySelectorAll("button")).map(x => x.textContent)).toEqual(others.map(v => v.label));
  const pick = Array.from(seg.querySelectorAll("button")).find(x => x.textContent === others[0].label)!;
  await act(async () => pick.click());
  expect(onRoute).toHaveBeenLastCalledWith({ baseline: others[0].name });
});

test("filmstrip is worst first and opens another item; inspector 422 shows the detail", async () => {
  const b = realBundle;
  const onRoute = await render(b);
  const strip = Array.from(host.querySelectorAll<HTMLButtonElement>(".filmstrip .fs"));
  expect(strip).toHaveLength(b.items[b.current].length);
  expect(strip.filter(s => s.classList.contains("cur")).map(s => s.dataset.id)).toEqual([b.focus]);
  const other = strip.find(s => s.dataset.id !== b.focus)!;
  await act(async () => other.click());
  expect(onRoute).toHaveBeenLastCalledWith({ item: other.dataset.id });

  stubFetch(b, url =>
    url.startsWith("/api/inspect/glcm") ? { status: 422, body: { detail: "GLCM cannot be measured on this slice: empty" } } : null,
  );
  const tab = Array.from(host.querySelectorAll<HTMLButtonElement>('[aria-label="Inspector"] button')).find(
    x => x.textContent === b.schema.inspectors.find(i => i.key === "glcm")!.label,
  )!;
  await act(async () => tab.click());
  await settle();
  expect(host.querySelector(".toolcard")?.textContent).toContain("cannot be measured on this slice: empty");
});

test("DatasetItem: an id with spaces round-trips into /api/items, /api/inspect and image URLs", async () => {
  const b = realBundle;
  stubFetch(b);
  const key = b.schema.dataset.key;
  await act(async () =>
    root.render(
      <DatasetItem
        schema={b.schema}
        route={{ section: "dataset", tab: "item", item: b.focus, version: b.current }}
        onRoute={vi.fn()}
      />,
    ),
  );
  await settle();
  expect(calls).toContain(`/api/items?dataset=${key}&version=${encodeURIComponent(b.current)}`);
  expect(calls).toContain(`/api/items?dataset=${key}&version=${encodeURIComponent(b.schema.dataset.default_baseline)}`);
  const inspect = calls.find(c => c.startsWith("/api/inspect/"))!;
  const q = new URL(inspect, "http://test.invalid").searchParams;
  expect(q.get("item")).toBe(b.focus);
  expect(q.get("dataset")).toBe(key);
  expect(q.get("version")).toBe(b.current);
  // spectrum compares the compare version with the current one
  expect(q.get("compare")).toBe(`${b.schema.dataset.default_baseline},${b.current}`);
  const srcs = Array.from(host.querySelectorAll<HTMLImageElement>(".panes img.base")).map(i => i.getAttribute("src")!);
  expect(srcs).toHaveLength(3);
  for (const s of srcs) {
    expect(s).toContain(`/${encodeURIComponent(b.focus)}/`);
    expect(s).not.toContain(" ");
    expect(new URL(s, "http://test.invalid").searchParams.get("dataset")).toBe(key);
  }
  expect(host.querySelector(".crumbs b")?.textContent).toBe(focusOf(b).label);
});

test("DatasetItem: switching the compare version keeps the screen while the new items load", async () => {
  const b = realBundle;
  const key = b.schema.dataset.key;
  const other = b.versions.find(v => v.name !== b.current && v.name !== b.schema.dataset.default_baseline)!.name;
  let release: () => void = () => {};
  const gate = new Promise<void>(r => (release = r));
  stubFetch(b);
  const base = globalThis.fetch as unknown as (url: string) => Promise<unknown>;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const u = new URL(url, "http://test.invalid");
      if (u.pathname === "/api/items" && u.searchParams.get("version") === other) await gate;
      return base(url);
    }),
  );
  const routeOf = (baseline?: string): Route => ({ section: "dataset", tab: "item", item: b.focus, version: b.current, baseline });
  const draw = (r: Route) => root.render(<DatasetItem schema={b.schema} route={r} onRoute={vi.fn()} />);
  await act(async () => draw(routeOf()));
  await settle();

  const second = b.schema.inspectors[1];
  const tabNamed = (text: string) =>
    Array.from(host.querySelectorAll<HTMLButtonElement>('[aria-label="Inspector"] button')).find(x => x.textContent === text)!;
  await act(async () => tabNamed(second.label).click());
  await settle();
  expect(tabNamed(second.label).getAttribute("aria-pressed")).toBe("true");

  await act(async () => draw(routeOf(other)));
  await settle();
  // the compare items are still loading: the screen stays, with the chosen tab
  expect(calls.some(c => c.startsWith(`/api/items?dataset=${key}&version=${encodeURIComponent(other)}`))).toBe(true);
  expect(host.querySelector(".filmstrip")).not.toBeNull();
  expect(tabNamed(second.label).getAttribute("aria-pressed")).toBe("true");

  await act(async () => release());
  await settle();
  expect(tabNamed(second.label).getAttribute("aria-pressed")).toBe("true");
  expect(host.querySelectorAll(".panes .pane")[1].textContent).toContain(label(b, other));
});

test("verdict panel hides the compare column when the compare version lacks the item", async () => {
  const b = realBundle;
  await render(b, { route: {} });
  expect(host.querySelectorAll(".mrow .cmp-val").length).toBeGreaterThan(0);
  await act(async () =>
    root.render(
      <ItemView
        schema={b.schema}
        versions={b.versions}
        version={b.current}
        items={b.items[b.current]}
        compare={b.baseline}
        compareItems={[]}
        route={{ section: "dataset", tab: "item", item: b.focus }}
        onRoute={vi.fn()}
      />,
    ),
  );
  expect(host.querySelectorAll(".mrow .cmp-val")).toHaveLength(0);
  expect(host.querySelector(".mhead")).toBeNull();
});

test("compare and current pane captions carry one status dot per axis", async () => {
  const b = stressBundle;
  await render(b);
  const panes = host.querySelectorAll(".panes .pane");
  const dots = (p: Element) => Array.from(p.querySelectorAll(".tri .dot")).map(d => d.getAttribute("title"));
  const statusLabel = (k: string) => b.schema.statuses.find(s => s.key === k)!.label;
  const expected = (it: Item) => b.schema.axes.map(a => `${a.label}: ${statusLabel(it.verdicts[a.key])}`);
  expect(dots(panes[0])).toEqual([]);
  expect(dots(panes[1])).toEqual(expected(focusOf(b, b.baseline)));
  expect(dots(panes[2])).toEqual(expected(focusOf(b)));
});
