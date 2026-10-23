import { describe, expect, test } from "vitest";
import type { Glcm, Spectrum } from "../api";
import { glcmDiff, spectrumSeries } from "./series";

describe("glcmDiff", () => {
  test("synthetic menos real, célula a célula", () => {
    const g: Glcm = {
      levels: 2,
      real: [[1, 0], [0, 0]],
      synthetic: [[0, 1], [0, 0]],
      tones: {
        real: { zero_pct: 0, top_pct: 0 },
        synthetic: { zero_pct: 0, top_pct: 0 },
      },
    };
    expect(glcmDiff(g)).toEqual([[-1, 1], [0, 0]]);
  });
});

describe("spectrumSeries", () => {
  const s: Spectrum = {
    freq: [0.1, 0.2, 0.3],
    real: [10, 5, 2],
    synthetic: [8, 4, 1],
    ref_p5: [1, 1, 1],
    ref_p95: [20, 20, 20],
    nyquist: 0.5,
  };

  test("duas linhas por frequência e uma faixa por frequência", () => {
    const out = spectrumSeries(s);
    expect(out.lines).toHaveLength(2 * 3);
    expect(out.band).toHaveLength(3);
    expect(out.lines.filter(p => p.which === "real")).toHaveLength(3);
    expect(out.band[0]).toEqual({ f: 0.1, lo: 1, hi: 20 });
  });

  test("valores nulos somem dos gráficos", () => {
    const out = spectrumSeries({ ...s, synthetic: [8, null, 1] as unknown as number[] });
    expect(out.lines).toHaveLength(5);
    expect(out.lines.some(p => p.which === "synthetic" && p.f === 0.2)).toBe(false);
  });
});
