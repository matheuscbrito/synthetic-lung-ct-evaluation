import { describe, expect, test } from "vitest";
import { DEFAULT_PREFS, loadAgentPrefs, saveAgentPrefs, MODELS } from "./agentState";

class MemoryStorage {
  private data = new Map<string, string>();
  getItem(key: string): string | null {
    return this.data.has(key) ? this.data.get(key)! : null;
  }
  setItem(key: string, value: string): void {
    this.data.set(key, value);
  }
}

class ThrowingStorage {
  getItem(): string | null {
    throw new Error("blocked");
  }
  setItem(): void {
    throw new Error("blocked");
  }
}

describe("agent prefs", () => {
  test("default model is Opus 5.5 and the panel starts open", () => {
    expect(DEFAULT_PREFS).toEqual({ open: true, model: "Opus 5.5" });
    expect(loadAgentPrefs(new MemoryStorage() as unknown as Storage)).toEqual({ open: true, model: "Opus 5.5" });
    expect(MODELS.map(m => m.name)).toEqual(["Fable 5.1", "Opus 5.5", "Sonnet 5.5", "Haiku 5.5"]);
  });

  test("setting the model persists and reloads", () => {
    const storage = new MemoryStorage() as unknown as Storage;
    saveAgentPrefs(storage, { model: "Haiku 5.5" });
    expect(loadAgentPrefs(storage).model).toBe("Haiku 5.5");
    expect(loadAgentPrefs(storage).open).toBe(true);
  });

  test("closed state persists and reloads", () => {
    const storage = new MemoryStorage() as unknown as Storage;
    saveAgentPrefs(storage, { open: false });
    expect(loadAgentPrefs(storage).open).toBe(false);
  });

  test("unknown stored model falls back to the default", () => {
    const storage = new MemoryStorage();
    storage.setItem("wb.agent.model", "GPT-9");
    expect(loadAgentPrefs(storage as unknown as Storage).model).toBe("Opus 5.5");
  });

  test("a throwing localStorage does not crash and falls back to defaults", () => {
    const storage = new ThrowingStorage() as unknown as Storage;
    expect(() => saveAgentPrefs(storage, { model: "Haiku 5.5" })).not.toThrow();
    expect(loadAgentPrefs(storage)).toEqual({ open: true, model: "Opus 5.5" });
  });

  test("missing storage (null) falls back to defaults", () => {
    expect(loadAgentPrefs(null)).toEqual({ open: true, model: "Opus 5.5" });
    expect(() => saveAgentPrefs(null, { open: false })).not.toThrow();
  });
});
