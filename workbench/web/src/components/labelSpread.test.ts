import { describe, expect, test } from "vitest";
import { spreadLabels, spreadValues } from "./labelSpread";

describe("spreadLabels", () => {
  test("leaves labels that are already far apart untouched", () => {
    expect(spreadLabels([10, 40, 90], 14)).toEqual([10, 40, 90]);
  });

  test("pushes colliding labels down so each is at least gap px below the previous", () => {
    expect(spreadLabels([10, 12, 16], 14)).toEqual([10, 24, 38]);
  });

  test("keeps the input order while spreading in vertical order", () => {
    expect(spreadLabels([30, 10, 12], 14)).toEqual([38, 10, 24]);
  });

  test("returns an empty array for no labels", () => {
    expect(spreadLabels([], 14)).toEqual([]);
  });
});

describe("spreadValues", () => {
  // escala log: 1 década = 100 px, valor maior fica mais acima (px menor)
  const toPx = (v: number) => (2 - Math.log10(v)) * 100;
  const fromPx = (p: number) => 10 ** (2 - p / 100);

  test("separates close log-scale values by at least the gap in pixels", () => {
    const [a, b] = spreadValues([1, 1.01], toPx, fromPx, 14);
    expect(Math.abs(toPx(b) - toPx(a))).toBeGreaterThanOrEqual(14 - 1e-9);
  });

  test("values far apart come back unchanged", () => {
    const out = spreadValues([1, 100], toPx, fromPx, 14);
    expect(out[0]).toBeCloseTo(1);
    expect(out[1]).toBeCloseTo(100);
  });
});
