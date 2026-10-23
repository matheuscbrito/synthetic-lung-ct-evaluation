import { describe, expect, test } from "vitest";
import { num } from "./format";

describe("num", () => {
  test("null prints dash", () => expect(num(null)).toBe("–"));
  test("non-finite prints dash", () => expect(num(Infinity)).toBe("–"));
  test("finite uses digits", () => {
    expect(num(1.23456)).toBe("1.23");
    expect(num(1.23456, 4)).toBe("1.2346");
  });
});
