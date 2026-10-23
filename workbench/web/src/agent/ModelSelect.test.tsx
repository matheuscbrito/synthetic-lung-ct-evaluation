// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { ModelSelect } from "./ModelSelect";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement;
let root: Root;

function pill(): HTMLButtonElement {
  return host.querySelector<HTMLButtonElement>(".mcur")!;
}

function option(name: string): HTMLButtonElement | undefined {
  return Array.from(host.querySelectorAll<HTMLButtonElement>(".mopt")).find(o => o.textContent?.includes(name));
}

function render(model: string, onModel: (m: string) => void) {
  act(() => {
    root.render(<ModelSelect model={model} onModel={onModel} />);
  });
}

beforeEach(() => {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
});

describe("ModelSelect", () => {
  test("clicking the pill opens the menu with the four models and ✓ on the current one", () => {
    render("Opus 5.5", () => {});
    expect(host.querySelector(".menu")).toBeNull();
    act(() => pill().click());
    expect(host.querySelector(".menu")).not.toBeNull();
    expect(pill().getAttribute("aria-expanded")).toBe("true");
    const names = Array.from(host.querySelectorAll(".mopt b")).map(b => b.textContent);
    expect(names).toEqual(["Fable 5.1", "Opus 5.5", "Sonnet 5.5", "Haiku 5.5"]);
    expect(option("Opus 5.5")!.getAttribute("aria-selected")).toBe("true");
    expect(option("Sonnet 5.5")!.getAttribute("aria-selected")).toBe("false");
  });

  test("choosing Sonnet 5.5 calls onModel and closes the menu", () => {
    const onModel = vi.fn();
    render("Opus 5.5", onModel);
    act(() => pill().click());
    act(() => option("Sonnet 5.5")!.click());
    expect(onModel).toHaveBeenCalledWith("Sonnet 5.5");
    expect(host.querySelector(".menu")).toBeNull();
  });

  test("Escape closes the open menu without choosing", () => {
    const onModel = vi.fn();
    render("Opus 5.5", onModel);
    act(() => pill().click());
    act(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });
    expect(host.querySelector(".menu")).toBeNull();
    expect(onModel).not.toHaveBeenCalled();
  });

  test("a mousedown outside the selector closes the menu", () => {
    render("Opus 5.5", () => {});
    act(() => pill().click());
    act(() => {
      document.body.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    });
    expect(host.querySelector(".menu")).toBeNull();
  });
});
