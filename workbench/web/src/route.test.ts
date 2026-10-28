import { describe, expect, test } from "vitest";
import { parseHash, toHash, type Route } from "./route";

describe("route hash", () => {
  test("round trip keeps spaces and dots in the item id", () => {
    const r: Route = {
      section: "dataset",
      tab: "item",
      dataset: "Same anatomy",
      item: "1.000000-P4P117S302I00009 Gated 60.0A-40067-1-047",
    };
    expect(parseHash(toHash(r))).toEqual(r);
  });

  test("round trip keeps three item ids in order", () => {
    const ids = [
      "1.000000-P4P117S302I00009 Gated 60.0A-40067-1-047",
      "1.000000-P4P117S302I00010 Gated 60.0A-40067-1-048",
      "0.5-P4P100 Gated 0.0A-1-058",
    ];
    const r: Route = { section: "dataset", tab: "compare", items: ids, axis: "texture" };
    expect(parseHash(toHash(r))).toEqual(r);
  });

  test("empty hash gives dataset/overview", () => {
    expect(parseHash("")).toEqual({ section: "dataset", tab: "overview" });
    expect(toHash({ section: "dataset", tab: "overview" })).toBe("#/dataset/overview");
  });

  test("empty dataset (or any empty scalar) counts as absent", () => {
    const r = parseHash("#/dataset/overview?dataset=&version=&item=x");
    expect(r).toEqual({ section: "dataset", tab: "overview", item: "x" });
    expect(toHash({ section: "dataset", tab: "overview", dataset: "" })).toBe("#/dataset/overview");
  });

  test("unknown section falls back to dataset/overview", () => {
    expect(parseHash("#/nope/whatever")).toEqual({ section: "dataset", tab: "overview" });
  });

  test("axis accepts any string", () => {
    expect(parseHash("#/generators/bench?axis=GLCM-contrast").axis).toBe("GLCM-contrast");
  });

  test("generators and versions sections are routable", () => {
    expect(parseHash("#/generators/runs").section).toBe("generators");
    expect(parseHash("#/versions/overview").section).toBe("versions");
  });

  test("unknown section resets the whole route, tab included", () => {
    expect(parseHash("#/nope/item")).toEqual({ section: "dataset", tab: "overview" });
    expect(parseHash("#/nope/item?item=A&dataset=B")).toEqual({ section: "dataset", tab: "overview" });
  });

  test("overview view mode round-trips and is optional", () => {
    const r: Route = { section: "dataset", tab: "overview", version: "v2-rs07", view: "matrix" };
    expect(toHash(r)).toContain("view=matrix");
    expect(parseHash(toHash(r))).toEqual(r);
    expect(parseHash("#/dataset/overview").view).toBeUndefined();
  });
});
