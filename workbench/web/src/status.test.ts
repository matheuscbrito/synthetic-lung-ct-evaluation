import { describe, expect, test } from "vitest";
import { neighbour, sortSlices } from "./status";
import type { Slice, Status } from "./api";

function mk(caseId: string, texture: Status, z = 0): Slice {
  return {
    case_id: caseId,
    label: caseId,
    patient: "?",
    pair_mode: "x",
    mask_only: false,
    brightness: { verdict: "approved", techniques: {} },
    texture: { verdict: texture, techniques: {} },
    metrics: [
      { key: "glcm_contrast", label: "GLCM contrast", group: "texture", technique: "GLCM",
        real: 0, synthetic: 0, value: z, z, status: texture, unit: "IQR" },
    ],
    density: { status: "ok", median_shift_iqr: 0 },
    wavelet_type: "textura preservada",
  };
}

describe("neighbour", () => {
  test("clamps at ends", () => {
    expect(neighbour(["a", "b", "c"], "a", -1)).toBe("a");
    expect(neighbour(["a", "b", "c"], "c", 1)).toBe("c");
    expect(neighbour(["a", "b", "c"], "b", 1)).toBe("c");
  });
});

describe("sortSlices", () => {
  test("worst first", () => {
    const s = [mk("x", "approved"), mk("y", "rejected"), mk("z", "review")];
    expect(sortSlices(s, "texture", "worst").map(x => x.case_id)).toEqual(["y", "z", "x"]);
  });

  test("worst breaks ties by max |z| then case id", () => {
    const s = [mk("b", "review", 1), mk("a", "review", 1), mk("c", "review", -3)];
    expect(sortSlices(s, "texture", "worst").map(x => x.case_id)).toEqual(["c", "a", "b"]);
  });
});
