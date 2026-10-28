import { describe, expect, test } from "vitest";
import { neighbour } from "./status";

describe("neighbour", () => {
  test("clamps at ends", () => {
    expect(neighbour(["a", "b", "c"], "a", -1)).toBe("a");
    expect(neighbour(["a", "b", "c"], "c", 1)).toBe("c");
    expect(neighbour(["a", "b", "c"], "b", 1)).toBe("c");
  });

  test("unknown id stays put", () => {
    expect(neighbour(["a", "b"], "z", 1)).toBe("z");
  });
});
