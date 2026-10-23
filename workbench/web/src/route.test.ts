import { describe, expect, test } from "vitest";
import { parseHash, toHash, type Route } from "./route";

describe("route hash", () => {
  test("hash round trip keeps spaces in case id", () => {
    const r = { view: "slice", version: "Dsr", caseId: "1.0-P4P100 Gated 0.0A-1-058", verdict: "texture" } as Route;
    expect(parseHash(toHash(r))).toEqual(r);
  });

  test("empty hash gives the default route", () => {
    expect(parseHash("")).toEqual({ view: "dataset", verdict: "texture" });
  });

  test("agent view is routable", () => {
    expect(parseHash("#/agent").view).toBe("agent");
    expect(toHash({ view: "agent", verdict: "texture" })).toBe("#/agent?verdict=texture");
  });

  test("unknown view falls back to dataset", () => {
    expect(parseHash("#/nope").view).toBe("dataset");
  });
});
