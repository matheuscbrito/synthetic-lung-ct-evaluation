import { describe, expect, test } from "vitest";
import type { Generator, VsBaseline } from "../api";
import { approvedLine, bestTexture, gainText, textureMetricKey } from "./boardRows";

function gen(name: string, approved: number | null, patch: Partial<Generator> = {}): Generator {
  return {
    name,
    mode: "x",
    is_baseline: false,
    counts: {
      brightness: { approved: 0, review: 0, rejected: 0 },
      texture: { approved: approved ?? 0, review: 0, rejected: 0 },
    },
    median_abs_z: {},
    vs_baseline: null,
    ...patch,
  };
}

const vs: VsBaseline = {
  indicator: "approved",
  label: "Texture approved",
  group: "texture",
  gain: 6,
  ci: [3, 9],
  result: "improved",
};

describe("bestTexture", () => {
  test("picks the candidate with most texture approvals and ignores the baseline", () => {
    const board = [
      gen("Dsr", 80, { is_baseline: true }),
      gen("wsr-haar-a", 14),
      gen("edm-sr-b", 9),
    ];
    expect(bestTexture(board)).toEqual({ name: "wsr-haar-a", approved: 14 });
  });

  test("null when there are no candidates (only the baseline)", () => {
    expect(bestTexture([gen("Dsr", 8, { is_baseline: true })])).toBeNull();
    expect(bestTexture([])).toBeNull();
  });

  test("ties keep the first candidate in board order", () => {
    expect(bestTexture([gen("A", 5), gen("B", 5)])).toEqual({ name: "A", approved: 5 });
  });
});

describe("approvedLine", () => {
  test("Texture approved before → after = signed difference", () => {
    expect(approvedLine(8, 14)).toBe("Texture approved 8 → 14 = +6");
  });

  test("negative and zero differences", () => {
    expect(approvedLine(14, 8)).toBe("Texture approved 14 → 8 = -6");
    expect(approvedLine(8, 8)).toBe("Texture approved 8 → 8 = 0");
  });
});

describe("gainText", () => {
  test("gain and CI with signs; missing bound shows an en dash", () => {
    expect(gainText(vs)).toBe("+6 [+3, +9]");
    expect(gainText({ ...vs, ci: [null, 9] })).toBe("+6 [–, +9]");
  });
});

describe("textureMetricKey", () => {
  test("prefers the metric chosen in the sort control, then the first texture metric", () => {
    const keys = ["delta_mu", "ll", "glcm_contrast", "wavelet_fine"];
    expect(textureMetricKey(keys, "wavelet_fine")).toBe("wavelet_fine");
    expect(textureMetricKey(keys, "worst")).toBe("glcm_contrast");
    expect(textureMetricKey(["delta_mu"], "history")).toBe("delta_mu");
    expect(textureMetricKey([], "history")).toBeNull();
  });
});
