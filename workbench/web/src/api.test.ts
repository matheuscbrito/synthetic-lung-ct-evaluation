import { describe, expect, test } from "vitest";
import { imageUrl, setImageToken } from "./api";

describe("imageUrl", () => {
  const id = "1.0 Gated 0.0A-058";
  test("encodes ids, adds token, reference window and dataset", () => {
    setImageToken(12.5);
    const url = imageUrl("ref", id, "real", 80, true, "Same set");
    expect(url).toContain(encodeURIComponent(id));
    expect(url).toContain("v=12.5");
    expect(url).toContain("window=reference");
    expect(url).toContain("size=80");
    expect(new URLSearchParams(url.split("?")[1]).get("dataset")).toBe("Same set");
    setImageToken(null);
    expect(imageUrl("ref", id, "real")).not.toContain("v=");
    expect(imageUrl("ref", id, "real")).not.toContain("dataset=");
  });
});
