// @vitest-environment jsdom
import { describe, expect, test } from "vitest";
import * as Observable from "@observablehq/plot";
import { heatmap } from "./GlcmTool";

// Matriz 32×32 com todas as células preenchidas: cada uma vira um retângulo.
function full(levels: number): number[][] {
  return Array.from({ length: levels }, (_, i) => Array.from({ length: levels }, (_, j) => (i + j) / 10));
}

function cellsOf(matrix: number[][]) {
  const out: { x: number; y: number; v: number }[] = [];
  matrix.forEach((row, i) => row.forEach((v, j) => out.push({ x: j, y: i, v })));
  return out;
}

describe("heatmap do GLCM", () => {
  test("renderiza 32×32 = 1024 células reais e sintéticas", () => {
    const levels = 32;
    for (const matrix of [full(levels), full(levels)]) {
      const options = heatmap("t", cellsOf(matrix), levels, { scheme: "viridis", domain: [0, 1] });
      const host = document.createElement("div");
      host.appendChild(Observable.plot(options));
      expect(host.querySelectorAll("rect")).toHaveLength(levels * levels);
    }
  });
});
