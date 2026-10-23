import { describe, expect, test } from "vitest";
import { OTHER, SERIES, seriesColor } from "./palette";

describe("seriesColor", () => {
  test("cor segue a posição da entidade na ordem estável", () => {
    expect(seriesColor("b", ["a", "b", "c"])).toBe(SERIES[1]);
  });

  test("desmarcar outra entidade não troca a cor de quem sobrou", () => {
    const order = ["a", "b", "c"];
    const before = seriesColor("b", order);
    // quem chama passa a mesma ordem estável mesmo com "a" desmarcada
    expect(seriesColor("b", order)).toBe(before);
  });

  test("a 9ª entidade cai no cinza 'Other', sem ciclar as cores", () => {
    const order = Array.from({ length: 9 }, (_, i) => `v${i}`);
    expect(seriesColor("v7", order)).toBe(SERIES[7]);
    expect(seriesColor("v8", order)).toBe(OTHER);
    expect(OTHER).toBe("#8a8f8c");
  });
});
