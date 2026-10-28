/// <reference types="vite/client" />
// Guarda de generalidade: o código da interface não nomeia métricas, técnicas, datasets nem pessoas do domínio;
// tudo isso chega pelo contrato (schema, itens, payloads). Fixtures e testes ficam de fora.
import { expect, test } from "vitest";

const SOURCES = import.meta.glob<string>(["./**/*.{ts,tsx,css}", "!./fixtures/**", "!./**/*.test.*"], {
  query: "?raw",
  import: "default",
  eager: true,
});
const FORBIDDEN = /\b(Dsr|Dgen|NEx|GLCM|NPS|Wavelet|GP-BO|Nelder|CADERNO|patient|Matheus|Lucas)\b/;

test("sources outside fixtures and tests never name domain metrics, datasets or people", () => {
  const paths = Object.keys(SOURCES);
  expect(paths.length).toBeGreaterThan(20);
  // CSS só chega com conteúdo por causa de `test.css.include` no vite.config.ts
  expect(paths.filter(p => p.endsWith(".css")).every(p => SOURCES[p].length > 0)).toBe(true);
  expect(paths.some(p => p.endsWith(".css"))).toBe(true);
  expect(paths.some(p => p.includes("/fixtures/") || p.includes(".test."))).toBe(false);
  const offenders = paths.flatMap(path =>
    SOURCES[path].split("\n").flatMap((line, i) => {
      const hit = line.match(FORBIDDEN);
      return hit ? [`${path}:${i + 1}: ${hit[0]}`] : [];
    }),
  );
  expect(offenders).toEqual([]);
});

test("the pattern catches each forbidden word and spares longer identifiers", () => {
  for (const word of ["Dsr", "Dgen", "NEx", "GLCM", "NPS", "Wavelet", "GP-BO", "Nelder", "CADERNO", "patient", "Matheus", "Lucas"]) {
    expect(FORBIDDEN.test(`a ${word} b`)).toBe(true);
  }
  expect(FORBIDDEN.test("patients")).toBe(false);
});
