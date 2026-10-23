// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import type { Notebook, NotebookRow } from "../api";
import { AgentView } from "./AgentView";

// Plot precisa de layout real; o teste verifica o comportamento da tela, não o desenho do gráfico.
vi.mock("../components/Plot", () => ({ Plot: () => null }));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

function row(partial: Partial<NotebookRow> & Pick<NotebookRow, "id">): NotebookRow {
  return {
    base: "baseline",
    change: "",
    gain_text: "",
    vals: [],
    scope: null,
    verdict: "",
    reason: "",
    best: false,
    search: "Matheus",
    ...partial,
  };
}

// Fixture pequena (não é o caderno real): duas tentativas, a segunda é a melhor atual.
const PARSED: Notebook["parsed"] = {
  searches: { M: "Matheus" },
  rows: [
    row({ id: "M1", change: "steps 50", verdict: "quase", gain_text: "n/d" }),
    row({ id: "M4", base: "M1", change: "eta 0,2", vals: [7.3, 5.3, 4.8], verdict: "melhor", best: true, reason: "melhor (29/8)" }),
  ],
  metrics: [{ name: "GLCM contraste", best: "+19,81%", other: "+11,94%" }],
  learned: [{ head: "eta: o parâmetro mais confiável.", body: "De 0 a 0,4 a melhora quase só sobe." }],
  next: ["eta 0,4 → 0,5."],
};

let host: HTMLDivElement;
let root: Root;

async function flush() {
  await act(async () => {
    await new Promise(r => setTimeout(r, 0));
  });
}

async function renderWith(body: Notebook) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => body }) as Response),
  );
  await act(async () => {
    root.render(<AgentView model="Opus 5.5" onModel={() => {}} />);
  });
  await flush();
}

function tabButton(label: string): HTMLButtonElement {
  return Array.from(host.querySelectorAll<HTMLButtonElement>("button.seg-opt")).find(b => b.textContent === label)!;
}

function detailTitle(): string | undefined {
  return host.querySelector(".xhead h2")?.textContent ?? undefined;
}

beforeEach(() => {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  window.location.hash = "";
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

describe("AgentView experiments", () => {
  test("opens on Experiments with the current best selected", async () => {
    await renderWith({ source: { path: "/lab/CADERNO.md", exists: true }, parsed: PARSED, raw: null });
    expect(host.textContent).toContain("Matheus's search · 2");
    expect(detailTitle()).toBe("M4 · eta 0,2");
  });

  test("clicking an attempt selects it and writes exp to the hash", async () => {
    await renderWith({ source: { path: "/lab/CADERNO.md", exists: true }, parsed: PARSED, raw: null });
    const m1 = Array.from(host.querySelectorAll<HTMLButtonElement>("button.xi")).find(b => b.textContent?.includes("steps 50"))!;
    await act(async () => m1.click());
    await flush();
    expect(window.location.hash).toContain("exp=M1");
    expect(detailTitle()).toBe("M1 · steps 50");
  });

  test("exp in the route selects that attempt", async () => {
    window.location.hash = "#/agent?exp=M1";
    await renderWith({ source: { path: "/lab/CADERNO.md", exists: true }, parsed: PARSED, raw: null });
    expect(detailTitle()).toBe("M1 · steps 50");
  });

  test("missing notebook: Runs is the default, and Experiments names the expected path", async () => {
    await renderWith({ source: { path: "/lab/CADERNO.md", exists: false }, parsed: null, raw: null });
    expect(host.textContent).toContain("No runs yet");
    await act(async () => tabButton("Experiments").click());
    await flush();
    expect(host.textContent).toContain("No notebook found at /lab/CADERNO.md");
  });

  test("unparsable notebook shows the raw markdown", async () => {
    await renderWith({ source: { path: "/lab/CADERNO.md", exists: true }, parsed: null, raw: "# bruto\n\ntexto" });
    expect(host.querySelector("pre.caderno-raw")?.textContent).toBe("# bruto\n\ntexto");
  });

  test("unreadable notebook shows the error line in the Experiments state", async () => {
    await renderWith({
      source: { path: "/lab/CADERNO.md", exists: true },
      parsed: null,
      raw: null,
      error: "sem permissão de leitura",
    });
    expect(host.textContent).toContain("sem permissão de leitura");
    expect(host.querySelector("pre.caderno-raw")).toBeNull();
  });

  test("experiment rows without numbers show the notebook text in the row title", async () => {
    await renderWith({
      source: { path: "/lab/CADERNO.md", exists: true },
      parsed: { ...PARSED!, rows: [row({ id: "M1", change: "steps 50", gain_text: "n/d (7 casos)", verdict: "insuficiente" })] },
      raw: null,
    });
    const item = host.querySelector<HTMLButtonElement>("button.xi")!;
    expect(item.querySelector(".xg")?.textContent).toBe("n/d (7 casos)");
    expect(item.title).toBe("n/d (7 casos)");
  });
});
