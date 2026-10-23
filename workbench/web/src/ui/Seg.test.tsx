// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { Seg } from "./Seg";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// geometria dos botões por rótulo: o teste muda a largura como uma troca de fonte faria
let geometry: Record<string, { left: number; width: number }> = {};

beforeEach(() => {
  geometry = {
    Texture: { left: 0, width: 60 },
    Brightness: { left: 60, width: 70 },
  };
  Object.defineProperty(HTMLElement.prototype, "offsetLeft", {
    configurable: true,
    get() {
      return geometry[this.textContent ?? ""]?.left ?? 0;
    },
  });
  Object.defineProperty(HTMLElement.prototype, "offsetWidth", {
    configurable: true,
    get() {
      return geometry[this.textContent ?? ""]?.width ?? 0;
    },
  });
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

let host: HTMLDivElement;
let root: Root;

const OPTIONS = [
  { value: "texture", label: "Texture" },
  { value: "brightness", label: "Brightness" },
] as const;

function thumb(): HTMLElement {
  return host.querySelector<HTMLElement>(".seg-thumb")!;
}

async function render(value: "texture" | "brightness") {
  await act(async () => {
    root.render(<Seg<"texture" | "brightness"> label="Verdict" options={[...OPTIONS]} value={value} onChange={() => {}} small />);
  });
}

// ResizeObserver falso: guarda o callback para o teste disparar, como o navegador faria ao redimensionar
class FakeResizeObserver {
  static instances: FakeResizeObserver[] = [];
  observed: Element[] = [];
  disconnected = false;
  constructor(private callback: () => void) {
    FakeResizeObserver.instances.push(this);
  }
  observe(el: Element) {
    this.observed.push(el);
  }
  disconnect() {
    this.disconnected = true;
  }
  fire() {
    this.callback();
  }
}

describe("Seg thumb", () => {
  test("follows the selected option", async () => {
    vi.stubGlobal("ResizeObserver", FakeResizeObserver);
    await render("brightness");
    expect(thumb().style.transform).toBe("translateX(60px)");
    expect(thumb().style.width).toBe("70px");
  });

  test("re-measures when the group resizes, not only when the window does", async () => {
    FakeResizeObserver.instances = [];
    vi.stubGlobal("ResizeObserver", FakeResizeObserver);
    await render("brightness");

    // fonte carregou: o segundo botão ficou mais largo e deslocado
    geometry.Brightness = { left: 90, width: 100 };
    await act(async () => {
      FakeResizeObserver.instances.forEach(o => o.fire());
    });
    expect(thumb().style.transform).toBe("translateX(90px)");
    expect(thumb().style.width).toBe("100px");
  });

  test("observes the group element and disconnects on unmount", async () => {
    FakeResizeObserver.instances = [];
    vi.stubGlobal("ResizeObserver", FakeResizeObserver);
    await render("texture");
    const group = host.querySelector(".seg");
    expect(FakeResizeObserver.instances.some(o => o.observed.includes(group!))).toBe(true);
    await act(async () => root.unmount());
    expect(FakeResizeObserver.instances.every(o => o.disconnected)).toBe(true);
    root = createRoot(host);
  });

  test("without ResizeObserver, falls back to the window resize event", async () => {
    vi.stubGlobal("ResizeObserver", undefined);
    await render("brightness");
    geometry.Brightness = { left: 80, width: 90 };
    await act(async () => {
      window.dispatchEvent(new Event("resize"));
    });
    expect(thumb().style.transform).toBe("translateX(80px)");
    expect(thumb().style.width).toBe("90px");
  });
});
