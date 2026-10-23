import { describe, expect, test } from "vitest";
import { OTHER, SERIES, divergingScale, foldSeries, sequentialScale, seriesColor, DIVERGING, SEQUENTIAL } from "./palette";

describe("seriesColor", () => {
  test("cor segue a posição da entidade na ordem estável", () => {
    expect(seriesColor("b", ["a", "b", "c"])).toBe(SERIES[1]);
  });

  test("desmarcar outra entidade não troca a cor de quem sobrou", () => {
    const order = ["a", "b", "c"];
    // "a" desmarcada: "b" continua com a cor da posição dela na ordem estável
    expect(foldSeries(["b", "c"], order).range[0]).toBe(SERIES[1]);
  });

  test("a 9ª entidade cai no cinza 'Other', sem ciclar as cores", () => {
    const order = Array.from({ length: 9 }, (_, i) => `v${i}`);
    expect(seriesColor("v7", order)).toBe(SERIES[7]);
    expect(seriesColor("v8", order)).toBe(OTHER);
    expect(OTHER).toBe("#8a8f8c");
  });
});

describe("foldSeries", () => {
  test("10 geradores: 8 cores próprias e uma única entrada 'Other (+2)' em cinza", () => {
    const order = Array.from({ length: 10 }, (_, i) => `v${i}`);
    const fold = foldSeries(order, order);
    expect(fold.domain).toHaveLength(9);
    expect(fold.range).toHaveLength(9);
    expect(fold.label(fold.domain[8])).toBe("Other (+2)");
    expect(fold.range[8]).toBe(OTHER);
    expect(fold.keyOf("v9")).toBe(fold.domain[8]);
    expect(fold.keyOf("v8")).toBe(fold.domain[8]);
    expect(fold.keyOf("v0")).toBe("v0");
  });

  test("sem excedente não há entrada 'Other'", () => {
    const order = ["a", "b"];
    expect(foldSeries(["a", "b"], order).domain).toEqual(["a", "b"]);
  });
});

describe("escalas", () => {
  test("sequencial usa as 7 paradas do ramp, casando domínio e range", () => {
    const scale = sequentialScale(0, 10);
    expect(scale.range).toEqual(SEQUENTIAL);
    expect(scale.domain).toHaveLength(SEQUENTIAL.length);
    expect(scale.domain[0]).toBe(0);
    expect(scale.domain[6]).toBe(10);
  });

  test("divergente: pivô em zero, meio neutro e domínio simétrico", () => {
    const scale = divergingScale(3);
    expect(scale.pivot).toBe(0);
    expect(scale.domain).toEqual([-3, 3]);
    expect(scale.range).toEqual([DIVERGING.neg, DIVERGING.mid, DIVERGING.pos]);
  });
});
