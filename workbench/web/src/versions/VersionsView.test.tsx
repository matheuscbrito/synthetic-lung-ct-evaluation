// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { realBundle, stressBundle, type Bundle } from "../fixtures";
import type { Route } from "../route";
import type { Schema } from "../contract/types";
import { clearContractCache } from "../contract/client";
import { VersionsView } from "./VersionsView";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;
let calls: { url: string; method: string; body?: unknown }[];

const enc = encodeURIComponent;

class Failure {
  constructor(
    public status: number,
    public detail: string,
  ) {}
}

// tabela pela URL completa (caminho + query) com o método; resposta de erro vira Failure
function mockApi(table: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      const body = typeof init?.body === "string" ? JSON.parse(init.body) : undefined;
      calls.push({ url, method, body });
      const key = `${method} ${url}`;
      if (!(key in table)) throw new Error(`unexpected ${key}`);
      const reply = table[key];
      if (reply instanceof Failure) {
        return { ok: false, status: reply.status, statusText: "Error", json: async () => ({ detail: reply.detail }) };
      }
      return { ok: true, status: 200, statusText: "OK", json: async () => reply };
    }),
  );
}

function baseTable(b: Bundle, extra: Record<string, unknown> = {}, detected: unknown = b.detected) {
  const k = enc(b.schema.dataset.key);
  return {
    [`GET /api/v2/versions?dataset=${k}`]: b.versions,
    [`GET /api/versions/detected?dataset=${k}`]: detected,
    "GET /api/runs": { runs: [{ key: "rs", label: "Random search" }] },
    ...extra,
  };
}

async function flush() {
  for (let i = 0; i < 5; i++) {
    await act(async () => {
      await new Promise(r => setTimeout(r, 0));
    });
  }
}

async function click(el: Element | null | undefined) {
  if (!el) throw new Error("element not found");
  await act(async () => {
    (el as HTMLElement).click();
  });
  await flush();
}

function typeInto(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
  act(() => {
    setter.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

async function render(schema: Schema, route: Partial<Route> = {}) {
  const onRoute = vi.fn();
  const onChanged = vi.fn();
  await act(async () =>
    root.render(
      <VersionsView
        schema={schema}
        route={{ section: "versions", tab: "overview", ...route }}
        onRoute={onRoute}
        onChanged={onChanged}
      />,
    ),
  );
  await flush();
  return { onRoute, onChanged };
}

const rows = () => Array.from(host.querySelectorAll<HTMLElement>('[role="list"][aria-label="Versions"] [role="listitem"]'));
const rowOf = (label: string) => rows().find(r => r.querySelector("b")?.textContent === label);
const buttonIn = (scope: Element, text: string) =>
  Array.from(scope.querySelectorAll("button")).find(b => b.textContent === text);
const buttonNamed = (text: string) => Array.from(host.querySelectorAll("button")).find(b => b.textContent === text);

beforeEach(() => {
  clearContractCache();
  calls = [];
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("stress-shaped versions: three rows labelled reference, baseline, RS-07", async () => {
  mockApi(baseTable(stressBundle));
  await render(stressBundle.schema);
  const labels = rows().map(r => r.querySelector("b")?.textContent);
  expect(labels).toHaveLength(3);
  expect(labels).toEqual(["reference", "baseline", "RS-07"]);
  expect(labels).toEqual(stressBundle.versions.map(v => v.label));
  // a referência não tem Remove e mostra a pílula; as demais têm Remove e a marca de avaliada
  expect(buttonIn(rowOf("reference")!, "Remove")).toBeUndefined();
  expect(rowOf("reference")!.querySelector(".pill")?.textContent).toBe("ruler reference");
  expect(buttonIn(rowOf("RS-07")!, "Remove")).toBeDefined();
  expect(host.querySelector("h1")?.textContent).toBe("Versions");
  expect(host.querySelector(".eyebrow")?.textContent).toBe(`History · ${stressBundle.schema.dataset.mode_label}`);
});

test("Edit id sends PATCH with the new label", async () => {
  const target = stressBundle.versions.find(v => v.label === "RS-07")!;
  const k = enc(stressBundle.schema.dataset.key);
  mockApi(
    baseTable(stressBundle, {
      [`PATCH /api/versions/${enc(target.name)}?dataset=${k}`]: { ...target, label: "RS-08" },
    }),
  );
  const { onChanged } = await render(stressBundle.schema);
  await click(buttonIn(rowOf("RS-07")!, "Edit id"));
  typeInto(host.querySelector<HTMLInputElement>('input[aria-label="Id for RS-07"]')!, "RS-08");
  await click(buttonIn(rowOf("RS-07")!, "Save"));
  const patch = calls.find(c => c.method === "PATCH");
  expect(patch).toEqual({ url: `/api/versions/${enc(target.name)}?dataset=${k}`, method: "PATCH", body: { label: "RS-08" } });
  expect(onChanged).toHaveBeenCalled();
});

test("a PATCH rejected by the API shows its detail inline", async () => {
  const target = stressBundle.versions.find(v => v.label === "RS-07")!;
  const k = enc(stressBundle.schema.dataset.key);
  mockApi(
    baseTable(stressBundle, {
      [`PATCH /api/versions/${enc(target.name)}?dataset=${k}`]: new Failure(400, "label already in use"),
    }),
  );
  await render(stressBundle.schema);
  await click(buttonIn(rowOf("RS-07")!, "Edit id"));
  typeInto(host.querySelector<HTMLInputElement>('input[aria-label="Id for RS-07"]')!, "RS-08");
  await click(buttonIn(rowOf("RS-07")!, "Save"));
  expect(rowOf("RS-07")!.textContent).toContain("label already in use");
});

test("no detected runs shows the empty state", async () => {
  mockApi(baseTable(stressBundle, {}, []));
  await render(stressBundle.schema);
  expect(host.textContent).toContain("No runs detected");
  expect(host.querySelector('[role="list"][aria-label="Detected runs"]')).toBeNull();
});

test("Add on a detected run posts name and folder, selects the new version and shows the message", async () => {
  const detected = stressBundle.detected[0];
  mockApi(
    baseTable(stressBundle, {
      [`POST /api/versions?dataset=${enc(stressBundle.schema.dataset.key)}`]: { message: "Added v3-rs12", name: "v3-rs12" },
    }),
  );
  const { onRoute, onChanged } = await render(stressBundle.schema);
  const list = host.querySelector('[role="list"][aria-label="Detected runs"]')!;
  expect(list.textContent).toContain(detected.name);
  await click(buttonIn(list, "Add"));
  expect(calls.find(c => c.method === "POST")?.body).toEqual({ name: detected.name, folder: detected.folder });
  expect(onRoute).toHaveBeenCalledWith({ version: "v3-rs12" });
  expect(host.querySelector('[role="status"]')?.textContent).toContain("Added v3-rs12");
  expect(onChanged).toHaveBeenCalled();
});

test("add form sends only the fields that were filled", async () => {
  mockApi(
    baseTable(stressBundle, {
      [`POST /api/versions?dataset=${enc(stressBundle.schema.dataset.key)}`]: { message: "Added", name: "auto-1" },
    }),
  );
  const { onRoute } = await render(stressBundle.schema);
  typeInto(host.querySelector<HTMLInputElement>('input[aria-label="Folder"]')!, "/data/sweeps/rs/0013");
  await click(buttonNamed("Add and evaluate"));
  expect(calls.find(c => c.method === "POST")?.body).toEqual({ folder: "/data/sweeps/rs/0013" });
  expect(onRoute).toHaveBeenCalledWith({ version: "auto-1" });
});

test("add form sends name and id when given", async () => {
  mockApi(
    baseTable(stressBundle, {
      [`POST /api/versions?dataset=${enc(stressBundle.schema.dataset.key)}`]: { message: "Added", name: "rs-13" },
    }),
  );
  await render(stressBundle.schema);
  typeInto(host.querySelector<HTMLInputElement>('input[aria-label="Version name"]')!, "rs-13");
  typeInto(host.querySelector<HTMLInputElement>('input[aria-label="Folder"]')!, "/data/sweeps/rs/0013");
  typeInto(host.querySelector<HTMLInputElement>('input[aria-label="Version id"]')!, "RS-13");
  await click(buttonNamed("Add and evaluate"));
  expect(calls.find(c => c.method === "POST")?.body).toEqual({ name: "rs-13", folder: "/data/sweeps/rs/0013", label: "RS-13" });
});

test("an add rejected by the API shows the error inline", async () => {
  mockApi(
    baseTable(stressBundle, {
      [`POST /api/versions?dataset=${enc(stressBundle.schema.dataset.key)}`]: new Failure(400, "folder does not exist"),
    }),
  );
  await render(stressBundle.schema);
  typeInto(host.querySelector<HTMLInputElement>('input[aria-label="Folder"]')!, "/nope");
  await click(buttonNamed("Add and evaluate"));
  expect(host.querySelector(".add-foot .tool-error")?.textContent).toBe("folder does not exist");
});

test("Remove asks for confirmation and sends DELETE", async () => {
  const target = stressBundle.versions.find(v => v.label === "RS-07")!;
  const k = enc(stressBundle.schema.dataset.key);
  mockApi(baseTable(stressBundle, { [`DELETE /api/versions/${enc(target.name)}?dataset=${k}`]: { message: "removed" } }));
  vi.spyOn(window, "confirm").mockReturnValue(false);
  await render(stressBundle.schema);
  await click(buttonIn(rowOf("RS-07")!, "Remove"));
  expect(calls.some(c => c.method === "DELETE")).toBe(false);
  vi.mocked(window.confirm).mockReturnValue(true);
  await click(buttonIn(rowOf("RS-07")!, "Remove"));
  expect(calls.some(c => c.method === "DELETE" && c.url === `/api/versions/${enc(target.name)}?dataset=${k}`)).toBe(true);
});

test("Recalculate posts refresh for the dataset and reloads", async () => {
  const k = enc(stressBundle.schema.dataset.key);
  mockApi(baseTable(stressBundle, { [`POST /api/refresh?dataset=${k}`]: { message: "refreshed" } }));
  const { onChanged } = await render(stressBundle.schema);
  await click(buttonNamed("Recalculate"));
  expect(calls.some(c => c.method === "POST" && c.url === `/api/refresh?dataset=${k}`)).toBe(true);
  expect(onChanged).toHaveBeenCalled();
});

test("dataset switch is hidden with one dataset and lists labels with several", async () => {
  mockApi(baseTable(stressBundle));
  await render(stressBundle.schema);
  expect(host.querySelector('[aria-label="Dataset"]')).toBeNull();

  const k = enc(realBundle.schema.dataset.key);
  mockApi(baseTable(realBundle, { [`GET /api/v2/versions?dataset=${k}`]: realBundle.versions }));
  const { onRoute } = await render(realBundle.schema);
  const group = host.querySelector('[aria-label="Dataset"]')!;
  expect(Array.from(group.querySelectorAll("button")).map(b => b.textContent)).toEqual(
    realBundle.schema.datasets.map(d => d.label),
  );
  await click(buttonIn(group, realBundle.schema.datasets[1].label));
  expect(onRoute).toHaveBeenCalledWith({ dataset: realBundle.schema.datasets[1].key, version: undefined });
});

test("header and add footnote name the reference and the axes", async () => {
  mockApi(baseTable(stressBundle));
  await render(stressBundle.schema);
  const ref = stressBundle.versions.find(v => v.is_reference)!.label;
  const axes = stressBundle.schema.axes.map(a => a.label.toLowerCase()).join(", ");
  expect(host.querySelector(".head .sub")?.textContent).toBe(`Each version is measured once against the ${ref} reference`);
  const addCard = Array.from(host.querySelectorAll(".eyebrow"))
    .find(e => e.textContent === "Add version")!
    .closest(".card")!;
  expect(addCard.lastElementChild?.textContent).toBe(`Adding a version validates the pairs against ${ref}, then measures ${axes} once.`);
});

test("a late add after a dataset switch neither routes nor shows a notice, and the new screen starts empty", async () => {
  const k1 = enc(stressBundle.schema.dataset.key);
  let answer!: (value: unknown) => void;
  const late = new Promise(resolve => {
    answer = resolve;
  });
  mockApi({
    ...baseTable(stressBundle, { [`POST /api/versions?dataset=${k1}`]: late }),
    ...baseTable(realBundle),
  });
  const first = await render(stressBundle.schema);
  typeInto(host.querySelector<HTMLInputElement>('input[aria-label="Folder"]')!, "/data/sweeps/rs/0014");
  await click(buttonNamed("Add and evaluate"));
  expect(host.querySelector(".vrow-pending")).not.toBeNull();

  const second = await render(realBundle.schema);
  expect(host.querySelector<HTMLInputElement>('input[aria-label="Folder"]')!.value).toBe("");
  expect(host.querySelector(".vrow-pending")).toBeNull();

  answer({ message: "Added late", name: "late" });
  await flush();
  expect(first.onRoute).not.toHaveBeenCalled();
  expect(second.onRoute).not.toHaveBeenCalled();
  expect(host.textContent).not.toContain("Added late");
  expect(host.querySelector('[role="status"]')).toBeNull();
});
