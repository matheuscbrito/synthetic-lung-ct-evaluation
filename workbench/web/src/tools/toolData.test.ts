import { beforeEach, describe, expect, test, vi } from "vitest";

const get = vi.hoisted(() => vi.fn());
vi.mock("../api", () => ({ get, toolPath: (v: string, c: string, t: string) => `/api/tools/${v}/${c}/${t}` }));

import { clearToolCache, loadTool } from "./toolData";

describe("tool cache", () => {
  beforeEach(() => {
    get.mockReset();
    clearToolCache();
  });

  test("shares a successful request until cleared, then refetches", async () => {
    get.mockResolvedValue({ freq: [] });
    await loadTool("Dsr", "case", "spectrum");
    await loadTool("Dsr", "case", "spectrum");
    expect(get).toHaveBeenCalledTimes(1);
    clearToolCache();
    await loadTool("Dsr", "case", "spectrum");
    expect(get).toHaveBeenCalledTimes(2);
  });
});
