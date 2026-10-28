// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import App from "./App";
import { clearContractCache } from "./contract/client";
import { realBundle } from "./fixtures";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;
let calls: { url: string; method: string }[];

function respond(body: unknown) {
  return { ok: true, status: 200, statusText: "OK", json: async () => body };
}

function schemaFor(key: string, hasHistory: boolean) {
  return { ...realBundle.schema, dataset: { ...realBundle.schema.dataset, key, has_history: hasHistory } };
}

// tabela pela URL completa (caminho + query); POST e GET não colidem porque o método também entra na conta
function mockApi(table: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      calls.push({ url, method });
      const key = `${method} ${url}`;
      if (key in table) return respond(table[key]);
      throw new Error(`unexpected ${key}`);
    }),
  );
}

async function flush() {
  for (let i = 0; i < 4; i++) {
    await act(async () => {
      await new Promise(r => setTimeout(r, 0));
    });
  }
}

function buttonNamed(text: string) {
  return Array.from(host.querySelectorAll("button")).find(b => b.textContent === text);
}

beforeEach(() => {
  clearContractCache();
  window.location.hash = "";
  calls = [];
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

test("a dataset without history shows the Evaluate button", async () => {
  mockApi({
    "GET /api/status": { stale: false, has_history: false, baseline: null, token: null },
    "GET /api/schema": schemaFor("Only", false),
  });
  await act(async () => root.render(<App />));
  await flush();
  expect(buttonNamed("Evaluate")).toBeDefined();
  expect(host.querySelector("nav")).toBeNull();
});

test("the route dataset decides the first-run gate and the init POST", async () => {
  window.location.hash = "#/dataset/overview?dataset=X";
  mockApi({
    "GET /api/status?dataset=X": { stale: false, has_history: false, baseline: null, token: 1 },
    "GET /api/status": { stale: false, has_history: true, baseline: "ref", token: 2 },
    "GET /api/schema?dataset=X": schemaFor("X", false),
    "POST /api/datasets/X/init": { message: "ok", name: "X" },
  });
  await act(async () => root.render(<App />));
  await flush();
  expect(buttonNamed("Evaluate")).toBeDefined();
  expect(calls.some(c => c.url === "/api/status" && c.method === "GET")).toBe(false);
  await act(async () => buttonNamed("Evaluate")!.click());
  await flush();
  expect(calls.some(c => c.method === "POST" && c.url === "/api/datasets/X/init")).toBe(true);
});

test("a stale dataset shows Recalculate and its click refreshes that dataset", async () => {
  window.location.hash = "#/dataset/overview?dataset=X";
  mockApi({
    "GET /api/status?dataset=X": { stale: true, has_history: true, baseline: "ref", token: 3 },
    "GET /api/schema?dataset=X": schemaFor("X", true),
    "POST /api/refresh?dataset=X": { message: "refreshed" },
  });
  await act(async () => root.render(<App />));
  await flush();
  expect(buttonNamed("Recalculate")).toBeDefined();
  await act(async () => buttonNamed("Recalculate")!.click());
  await flush();
  expect(calls.some(c => c.method === "POST" && c.url === "/api/refresh?dataset=X")).toBe(true);
});

// fetch pelo caminho: status, esquema, versões, itens e inspetores vêm do bundle real
function mockBundle() {
  const b = realBundle;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, method: init?.method ?? "GET" });
      const u = new URL(url, "http://test.invalid");
      let body: unknown;
      if (u.pathname === "/api/status") body = { stale: false, has_history: true, baseline: b.baseline, token: 7 };
      else if (u.pathname === "/api/schema") body = b.schema;
      else if (u.pathname === "/api/versions") body = b.versions;
      else if (u.pathname === "/api/items") {
        const version = u.searchParams.get("version")!;
        body = { version, items: b.items[version] };
      } else if (u.pathname.startsWith("/api/inspect/")) body = b.inspect[decodeURIComponent(u.pathname.slice(13))];
      else throw new Error(`unexpected ${url}`);
      return respond(body);
    }),
  );
}

test("the item tab renders the item screen for the route item", async () => {
  const b = realBundle;
  window.location.hash = `#/dataset/item?item=${encodeURIComponent(b.focus)}&version=${encodeURIComponent(b.current)}`;
  mockBundle();
  await act(async () => root.render(<App />));
  await flush();
  await flush();
  expect(host.querySelector(".item-view .crumbs b")?.textContent).toBe(b.items[b.current].find(i => i.id === b.focus)!.label);
  expect(host.querySelector(".placeholder")).toBeNull();
});

test("the compare tab renders the compare screen", async () => {
  window.location.hash = "#/dataset/compare";
  mockBundle();
  await act(async () => root.render(<App />));
  await flush();
  await flush();
  expect(host.querySelector(".compare-view")).not.toBeNull();
  expect(host.querySelector(".placeholder")).toBeNull();
});
