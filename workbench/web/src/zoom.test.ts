import { describe, expect, test } from "vitest";
import { pan, zoomAt } from "./zoom";

describe("zoom e pan sincronizados", () => {
  test("zoom de 2× em (100,100) mantém o ponto sob o cursor", () => {
    expect(zoomAt({ scale: 1, x: 0, y: 0 }, 2, 100, 100)).toEqual({ scale: 2, x: -100, y: -100 });
  });

  test("zoom repetido satura em 8", () => {
    let v = { scale: 1, x: 0, y: 0 };
    for (let i = 0; i < 100; i++) v = zoomAt(v, 1.2, 50, 50);
    expect(v.scale).toBe(8);
  });

  test("zoom abaixo de 1 não sai de 1", () => {
    expect(zoomAt({ scale: 1, x: 0, y: 0 }, 0.5, 30, 30).scale).toBe(1);
  });

  test("pan soma o deslocamento sem mudar a escala", () => {
    expect(pan({ scale: 2, x: -10, y: 5 }, 3, -4)).toEqual({ scale: 2, x: -7, y: 1 });
  });
});
