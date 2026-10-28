import { describe, expect, test } from "vitest";
import { toggle } from "./selection";

describe("toggle", () => {
  test("ignora um quinto id", () => {
    let set = new Set<string>();
    for (const id of ["a", "b", "c", "d"]) set = toggle(set, id);
    set = toggle(set, "e");
    expect(set.size).toBe(4);
    expect(set.has("e")).toBe(false);
  });

  test("remove um id já selecionado", () => {
    const set = toggle(new Set(["a", "b"]), "a");
    expect([...set]).toEqual(["b"]);
  });

  test("não altera o conjunto recebido", () => {
    const before = new Set(["a"]);
    toggle(before, "b");
    expect([...before]).toEqual(["a"]);
  });
});
