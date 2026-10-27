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

function respond(body: unknown) {
  return { ok: true, status: 200, statusText: "OK", json: async () => body };
}

beforeEach(() => {
  clearContractCache();
  window.location.hash = "";
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
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.startsWith("/api/status")) return respond({ stale: false, has_history: false, baseline: null, token: null });
      if (url.startsWith("/api/schema")) return respond({ ...realBundle.schema, dataset: { ...realBundle.schema.dataset, has_history: false } });
      throw new Error(`unexpected ${url}`);
    }),
  );
  await act(async () => {
    root.render(<App />);
  });
  await act(async () => {
    await new Promise(r => setTimeout(r, 0));
  });
  const button = Array.from(host.querySelectorAll("button")).find(b => b.textContent === "Evaluate");
  expect(button).toBeDefined();
  expect(host.querySelector("nav")).toBeNull();
});
