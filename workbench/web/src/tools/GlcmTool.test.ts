// @vitest-environment jsdom
import { describe, expect, test } from "vitest";
import * as Observable from "@observablehq/plot";
import { heatmap } from "./GlcmTool";
import { DIVERGING, SEQUENTIAL, divergingScale, sequentialScale } from "../palette";

// Plot escreve as cores como rgb(r, g, b); a comparação é feita no mesmo formato.
function rgb(hex: string): string {
  const n = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16));
  return `rgb(${n.join(", ")})`;
}

function fillsOf(values: number[], color: Parameters<typeof heatmap>[3]): (string | null)[] {
  const cells = values.map((v, x) => ({ x, y: 0, v }));
  const host = document.createElement("div");
  host.appendChild(Observable.plot(heatmap("t", cells, values.length, color)));
  return [...host.querySelectorAll("rect")].map(r => r.getAttribute("fill"));
}

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

  test("sequencial usa as 7 paradas: cada valor do domínio cai numa parada da escala", () => {
    const scale = sequentialScale(0, 6);
    const fills = fillsOf(scale.domain, scale);
    expect(fills).toEqual(SEQUENTIAL.map(rgb));
  });

  test("divergente: zero cai no meio neutro e os extremos nos polos", () => {
    const scale = divergingScale(2);
    const fills = fillsOf([-2, 0, 2], scale);
    expect(fills).toEqual([DIVERGING.neg, DIVERGING.mid, DIVERGING.pos].map(rgb));
  });
});
