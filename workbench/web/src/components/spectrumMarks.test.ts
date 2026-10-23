import { describe, expect, test } from "vitest";
import { spectrumYDomain } from "./spectrumMarks";

describe("spectrumYDomain", () => {
  test("spans whole decades from the lowest value up to the top", () => {
    expect(spectrumYDomain([{ f: 0.1, lo: 0.004, hi: 0.2 }], [{ power: 0.05 }], 0.2)).toEqual([0.001, 1]);
  });

  test("never returns a zero-width domain", () => {
    const [lo, hi] = spectrumYDomain([], [{ power: 10 }], 10);
    expect(hi).toBeGreaterThan(lo);
  });
});
