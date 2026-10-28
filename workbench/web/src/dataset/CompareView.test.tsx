// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { stressBundle as b } from "../fixtures";
import type { Route } from "../route";
import { CompareView } from "./CompareView";
import { focusAxis } from "./strip";

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

// Respostas do contrato a partir do fixture de stress; cada chamada registrada em `calls`.
function stubFetch(calls: string[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      calls.push(url);
      const path = new URL(url, "http://workbench.test");
      let body: unknown;
      if (path.pathname === "/api/v2/versions") body = b.versions;
      else if (path.pathname === "/api/items") body = { version: path.searchParams.get("version"), items: b.items[b.current] };
      else if (path.pathname.startsWith("/api/inspect/")) body = b.inspect[path.pathname.split("/").pop()!];
      else throw new Error(`unexpected ${url}`);
      return { ok: true, status: 200, statusText: "OK", json: async () => body };
    }),
  );
}

// Deixa as respostas simuladas e as atualizações do React assentarem.
async function flush() {
  for (let i = 0; i < 5; i++) {
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });
  }
}

async function render(route: Partial<Route> = {}, onRoute = vi.fn()) {
  const full: Route = { section: "dataset", tab: "compare", version: b.current, ...route };
  await act(async () => root.render(<CompareView schema={b.schema} route={full} onRoute={onRoute} />));
  await flush();
  return onRoute;
}

const items = b.items[b.current];
const labelOf = (id: string) => items.find(it => it.id === id)!.label;
const columns = () => Array.from(host.querySelectorAll<HTMLElement>(".ccol"));

test("three named items: three columns, one metric row per metric, legend labels are the item labels", async () => {
  stubFetch([]);
  const ids = b.compare_items;
  await render({ items: ids });

  const labels = ids.map(labelOf);
  expect(columns()).toHaveLength(3);
  expect(columns().map(col => col.querySelector("b")?.textContent)).toEqual(labels);
  for (const col of columns()) {
    expect(col.querySelectorAll(".crow")).toHaveLength(b.schema.metrics.length);
  }
  const legend = Array.from(host.querySelectorAll(".chart-curves .lab"))
    .map(node => node.textContent)
    .filter(text => text !== "Real");
  expect(legend).toEqual(labels);
});

test("without route items: at most three columns, one per status present on the focus axis", async () => {
  stubFetch([]);
  await render({});

  const axis = focusAxis(items, b.schema);
  const statuses = new Set(items.map(it => it.verdicts[axis]));
  expect(columns()).toHaveLength(Math.min(3, statuses.size));
});

test("the overlay asks the inspector once per item and never sends compare", async () => {
  const calls: string[] = [];
  stubFetch(calls);
  const ids = b.compare_items;
  await render({ items: ids });

  const inspect = calls.filter(url => url.startsWith("/api/inspect/"));
  expect(inspect).toHaveLength(ids.length);
  ids.forEach((id, i) => {
    expect(new URLSearchParams(inspect[i].split("?")[1]).get("item")).toBe(id);
  });
  expect(inspect.some(url => url.includes("compare="))).toBe(false);
});
