import { beforeEach, describe, expect, test, vi } from "vitest";

const get = vi.hoisted(() => vi.fn());
vi.mock("./api", () => ({ get }));

import { clearSlicesCache, slicesOf } from "./slices";

describe("slices cache", () => {
  beforeEach(() => {
    get.mockReset();
    clearSlicesCache();
  });

  test("one request per version until cleared", async () => {
    get.mockResolvedValue({ version: "Dsr", n_cases: 1, slices: [{ case_id: "a" }] });
    await slicesOf("Dsr");
    await slicesOf("Dsr");
    expect(get).toHaveBeenCalledTimes(1);
    expect(get).toHaveBeenCalledWith("/api/slices", { version: "Dsr" });
  });

  test("refetches after clearSlicesCache", async () => {
    get.mockResolvedValueOnce({ version: "Dsr", n_cases: 1, slices: [{ case_id: "old" }] });
    get.mockResolvedValueOnce({ version: "Dsr", n_cases: 1, slices: [{ case_id: "new" }] });
    expect((await slicesOf("Dsr"))[0].case_id).toBe("old");
    clearSlicesCache();
    expect((await slicesOf("Dsr"))[0].case_id).toBe("new");
    expect(get).toHaveBeenCalledTimes(2);
  });

  test("failed request is not cached", async () => {
    get.mockRejectedValueOnce(new Error("boom"));
    get.mockResolvedValueOnce({ version: "Dsr", n_cases: 0, slices: [] });
    await expect(slicesOf("Dsr")).rejects.toThrow("boom");
    await expect(slicesOf("Dsr")).resolves.toEqual([]);
    expect(get).toHaveBeenCalledTimes(2);
  });
});
