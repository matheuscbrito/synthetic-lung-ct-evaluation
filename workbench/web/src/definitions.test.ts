import { describe, expect, test } from "vitest";
import { imageUrl, setImageToken } from "./api";
import { waveletType } from "./definitions";

describe("waveletType", () => {
  test("covers every framework label in English", () => {
    for (const label of ["textura preservada", "borrou", "ruído", "estourou", "perdeu contraste", "ganhou contraste"]) {
      expect(waveletType(label)).toMatch(/^[a-z ]+$/);
      expect(waveletType(label)).not.toBe(label);
    }
    expect(waveletType("outro")).toBe("outro");
  });
});

describe("imageUrl", () => {
  const id = "1.0 Gated 0.0A-058";
  test("encodes ids, adds token and reference window", () => {
    setImageToken(12.5);
    const url = imageUrl("Dsr", id, "real", 80, true);
    expect(url).toContain(encodeURIComponent(id));
    expect(url).toContain("v=12.5");
    expect(url).toContain("window=reference");
    expect(url).toContain("size=80");
    setImageToken(null);
    expect(imageUrl("Dsr", id, "real")).not.toContain("v=");
  });
});
