// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { clearContractCache, contractKey, setContractToken, useContract } from "./client";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

type Seen = { data: { v: string } | null; error: string | null };
let host: HTMLDivElement;
let root: Root;
let seen: Seen[];
let pending: Map<string, (body: unknown) => void>;
let fetchMock: ReturnType<typeof vi.fn>;

function Probe({ params }: { params: Record<string, string> }) {
  const state = useContract<{ v: string }>("/api/items", params);
  seen.push(state);
  return null;
}

const last = () => seen[seen.length - 1];

beforeEach(() => {
  clearContractCache();
  setContractToken(null);
  seen = [];
  pending = new Map();
  fetchMock = vi.fn(
    (url: string) =>
      new Promise((resolve) => {
        pending.set(url, (body) => resolve({ ok: true, status: 200, statusText: "OK", json: async () => body }));
      }),
  );
  vi.stubGlobal("fetch", fetchMock);
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

describe("contractKey", () => {
  test("sorts params and includes the token", () => {
    expect(contractKey("/api/x", { b: "2", a: "1" })).toBe(contractKey("/api/x", { a: "1", b: "2" }));
    const k = contractKey("/api/x", { a: "1" });
    setContractToken(7);
    expect(contractKey("/api/x", { a: "1" })).not.toBe(k);
  });
});

describe("useContract", () => {
  test("a late response for an old key never overwrites the current one", async () => {
    await act(async () => root.render(<Probe params={{ dataset: "A", version: "v1" }} />));
    await act(async () => root.render(<Probe params={{ dataset: "A", version: "v2" }} />));
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [first, second] = fetchMock.mock.calls.map((c) => c[0] as string);
    expect(first).toContain("version=v1");
    expect(second).toContain("version=v2");

    await act(async () => pending.get(second)!({ v: "second" }));
    expect(last().data).toEqual({ v: "second" });
    await act(async () => pending.get(first)!({ v: "first" }));
    expect(last().data).toEqual({ v: "second" });
    expect(last().error).toBeNull();
  });

  test("cached keys are served without refetching and data of another key is never shown", async () => {
    await act(async () => root.render(<Probe params={{ version: "v1" }} />));
    const url1 = fetchMock.mock.calls[0][0] as string;
    await act(async () => pending.get(url1)!({ v: "one" }));
    await act(async () => root.render(<Probe params={{ version: "v2" }} />));
    expect(last().data).toBeNull();
    await act(async () => root.render(<Probe params={{ version: "v1" }} />));
    expect(last().data).toEqual({ v: "one" });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  test("errors are reported and the token change refetches", async () => {
    fetchMock.mockImplementationOnce(async () => ({ ok: false, status: 404, statusText: "Not Found", json: async () => ({ detail: "no such item" }) }));
    await act(async () => root.render(<Probe params={{ version: "v1" }} />));
    expect(last()).toEqual({ data: null, error: "no such item" });
    await act(async () => setContractToken(3));
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
