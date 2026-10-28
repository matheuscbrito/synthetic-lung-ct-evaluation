// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { clearContractCache } from "../contract/client";
import { realBundle } from "../fixtures";
import type { Route } from "../route";
import { GeneratorNotebook } from "./Notebook";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;

beforeEach(() => {
  clearContractCache();
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(realBundle.experiments), { status: 200, headers: { "Content-Type": "application/json" } })),
  );
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

const schema = realBundle.schema;
const exps = realBundle.experiments!.experiments;

async function render(route: Partial<Route> = {}, onRoute = vi.fn()) {
  const full: Route = { section: "generators", tab: "exp", ...route };
  await act(async () => {
    root.render(<GeneratorNotebook schema={schema} route={full} onRoute={onRoute} />);
  });
  // the contract client resolves the fetch in a later microtask
  for (let i = 0; i < 5 && !host.querySelector(".nb"); i++) {
    await act(async () => {
      await new Promise(r => setTimeout(r, 0));
    });
  }
  return onRoute;
}

const items = () => Array.from(host.querySelectorAll<HTMLButtonElement>(".nb-item"));

test("lists every experiment in source order with one star on the best", async () => {
  await render();
  expect(items().map(b => b.querySelector(".nb-id")?.textContent)).toEqual(exps.map(e => e.id));
  const stars = host.querySelectorAll(".nb-best");
  expect(stars).toHaveLength(exps.filter(e => e.is_best).length);
  expect(items().find(b => b.querySelector(".nb-best"))?.querySelector(".nb-id")?.textContent).toBe("M12");
});

test("the detail shows the selected experiment, its lineage and the current best tag", async () => {
  await render({ exp: "M12" });
  expect(host.querySelector(".nb-detail h2")?.textContent).toContain("M12");
  expect(host.textContent).toContain("Current best");
  const chips = Array.from(host.querySelectorAll(".nb-ln")).map(c => c.textContent);
  expect(chips).toEqual(["M4", "M6", "M7", "M8", "M10", "M11", "M12"]);
});

test("clicking a list item routes to that experiment", async () => {
  const onRoute = await render({ exp: "M12" });
  const l2 = items().find(b => b.querySelector(".nb-id")?.textContent === "L2")!;
  await act(async () => l2.click());
  expect(onRoute).toHaveBeenCalledWith({ exp: "L2" });
});

test("the search box narrows the list", async () => {
  await render();
  const box = host.querySelector<HTMLInputElement>('input[type="search"]')!;
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    setter.call(box, "superada");
    box.dispatchEvent(new Event("input", { bubbles: true }));
  });
  expect(items().map(b => b.querySelector(".nb-id")?.textContent)).toEqual(["L9"]);
});

test("the trajectory chart draws both lineages with the goal line", async () => {
  await render({ exp: "M12" });
  expect(host.querySelectorAll(".nb-path")).toHaveLength(2);
  expect(host.querySelector(".nb-goal")).not.toBeNull();
});
