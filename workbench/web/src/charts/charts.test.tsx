// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, test } from "vitest";
import type {
  CurvesPayload,
  ImagePayload,
  InspectorDesc,
  InspectorPayload,
  IntervalPayload,
  MatrixPayload,
} from "../contract/types";
import { bundles } from "../fixtures";
import { SERIES } from "../palette";
import { InspectorChart } from "./index";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
});

function render(desc: InspectorDesc, payload: InspectorPayload, colors?: Record<string, string>) {
  act(() => root.render(<InspectorChart desc={desc} payload={payload} colors={colors} />));
}

// todo par (descritor, payload) dos dois fixtures, inclusive o da comparação
const cases = Object.entries(bundles).flatMap(([name, b]) => [
  ...b.schema.inspectors
    .filter(d => b.inspect[d.key])
    .map(d => [`${name} · ${d.key}`, d, b.inspect[d.key]] as const),
  [
    `${name} · compare ${b.compare_inspect.inspector}`,
    b.schema.inspectors.find(d => d.key === b.compare_inspect.inspector)!,
    b.compare_inspect.payload,
  ] as const,
]);

describe("InspectorChart", () => {
  test.each(cases)("renders %s without throwing", (_, desc, payload) => {
    render(desc, payload);
    expect(host.querySelector(`.chart-${desc.chart}`)).not.toBeNull();
  });

  test("every chart type of the fixtures is covered", () => {
    const kinds = new Set(cases.map(([, d]) => d.chart));
    for (const k of ["curves", "bars", "interval", "matrix"]) expect(kinds.has(k as never)).toBe(true);
  });
});

function curvesCase(): [InspectorDesc, CurvesPayload] {
  const b = bundles.real;
  const desc = b.schema.inspectors.find(d => d.chart === "curves")!;
  return [desc, b.inspect[desc.key] as CurvesPayload];
}

describe("Curves", () => {
  test("the real series is drawn in ink, the others from the palette by order", () => {
    const [desc, p] = curvesCase();
    const payload: CurvesPayload = {
      ...p,
      series: [
        { ...p.series[0], label: "A", role: "version" },
        { ...p.series[0], label: "Real", role: "real" },
        { ...p.series[0], label: "B", role: "item" },
      ],
    };
    render(desc, payload);
    const stroke = (label: string) =>
      (host.querySelector(`path.line[data-label="${label}"]`) as SVGPathElement).style.stroke;
    expect(stroke("Real")).toBe("var(--ink2)");
    expect(stroke("A")).toBe(SERIES[0]);
    expect(stroke("B")).toBe(SERIES[1]);
  });

  test("colors override the palette but never the real series", () => {
    const [desc, p] = curvesCase();
    const payload: CurvesPayload = {
      ...p,
      series: [
        { ...p.series[0], label: "Real", role: "real" },
        { ...p.series[0], label: "A", role: "version" },
      ],
    };
    render(desc, payload, { A: "#123456", Real: "#654321" });
    expect((host.querySelector('path.line[data-label="A"]') as SVGPathElement).style.stroke).toBe("#123456");
    expect((host.querySelector('path.line[data-label="Real"]') as SVGPathElement).style.stroke).toBe("var(--ink2)");
  });

  test("end labels are at least 14 px apart", () => {
    const [desc, p] = curvesCase();
    const flat = { ...p.series[0], y: p.series[0].y.map(() => 1) };
    const payload: CurvesPayload = {
      ...p,
      y: { ...p.y, scale: "linear" },
      band: null,
      series: ["A", "B", "C"].map(label => ({ ...flat, label, role: "version" as const })),
    };
    render(desc, payload);
    const ys = [...host.querySelectorAll("text.lab")].map(t => Number(t.getAttribute("y"))).sort((a, b) => a - b);
    expect(ys).toHaveLength(3);
    for (let i = 1; i < ys.length; i++) expect(ys[i] - ys[i - 1]).toBeGreaterThanOrEqual(14 - 1e-6);
  });

  test("log y prints powers of ten; null points split the line without moving the others", () => {
    const [desc, p] = curvesCase();
    const payload: CurvesPayload = {
      x: { label: "x" },
      y: { label: "y", scale: "log" },
      band: null,
      markers: [],
      series: [{ label: "A", role: "version", x: [1, 2, 3, 4], y: [10, null, 100, 1000] }],
    };
    render(desc, payload);
    expect(host.querySelector("text.ax tspan")?.textContent).toMatch(/^\d+$/);
    const d = host.querySelector('path.line[data-label="A"]')!.getAttribute("d")!;
    expect(d.match(/M/g)).toHaveLength(2);
    expect(p).toBeDefined();
  });
});

describe("Interval", () => {
  function pointAndBands(desc: InspectorDesc, p: IntervalPayload) {
    render(desc, p);
    const pt = host.querySelector("circle.pt")!;
    const bands = [...host.querySelectorAll("rect.iband")].map((r, i) => ({
      band: p.bands[i],
      a: Number(r.getAttribute("x")),
      z: Number(r.getAttribute("x")) + Number(r.getAttribute("width")),
    }));
    return { cx: Number(pt.getAttribute("cx")), status: pt.getAttribute("data-status"), bands };
  }
  const inside = (cx: number, b: { a: number; z: number }) => cx >= b.a - 1e-6 && cx <= b.z + 1e-6;

  // a posição é a do valor; a cor é a do status do payload (que pode vir do IC e não da faixa), senão a da faixa
  test.each(Object.keys(bundles) as ("real" | "stress")[])("%s: the point sits in the band holding its value, in its status", name => {
    const b = bundles[name];
    const desc = b.schema.inspectors.find(d => d.chart === "interval")!;
    const p = b.inspect[desc.key] as IntervalPayload;
    const { cx, status, bands } = pointAndBands(desc, p);
    const holding = bands.filter(x => p.value! >= x.band.from && p.value! <= x.band.to);
    expect(holding.length).toBeGreaterThan(0);
    expect(holding.some(x => inside(cx, x))).toBe(true);
    // sem status no payload, o ponto toma o status da faixa que contém o valor
    expect(status).toBe(p.status ?? holding[0].band.status);
  });

  test("the point sits inside the band of its status", () => {
    const b = bundles.stress;
    const desc = b.schema.inspectors.find(d => d.chart === "interval")!;
    const p = b.inspect[desc.key] as IntervalPayload;
    const { cx, bands } = pointAndBands(desc, p);
    expect(bands.filter(x => x.band.status === p.status).some(x => inside(cx, x))).toBe(true);
  });

  test("without a status the point takes the status of the band it falls in", () => {
    const desc: InspectorDesc = { key: "i", label: "I", chart: "interval" };
    const p: IntervalPayload = {
      value: 0.5,
      ci: null,
      bands: [
        { from: -2, to: 0, status: "rejected" },
        { from: 0, to: 2, status: "approved" },
      ],
    };
    render(desc, p);
    expect(host.querySelector("circle.pt")!.getAttribute("data-status")).toBe("approved");
  });

  test("a missing value prints n/a and draws no point", () => {
    const desc: InspectorDesc = { key: "i", label: "I", chart: "interval" };
    render(desc, { value: null, ci: null, bands: [{ from: -1, to: 1, status: "approved" }] });
    expect(host.querySelector("circle.pt")).toBeNull();
    expect(host.textContent).toContain("n/a");
  });
});

describe("Bars", () => {
  test("a null bar keeps its slot and label but draws no rect", () => {
    const desc: InspectorDesc = { key: "b", label: "B", chart: "bars" };
    render(desc, {
      y: { label: "y" },
      zero: 0,
      bars: [
        { label: "a", value: 1 },
        { label: "b", value: null },
        { label: "c", value: -1 },
      ],
    });
    expect(host.querySelectorAll("rect.wbar")).toHaveLength(2);
    const labels = [...host.querySelectorAll("text.blab")].map(t => t.textContent);
    expect(labels).toEqual(["a", "b", "c"]);
  });
});

describe("Matrix", () => {
  test.each(Object.keys(bundles) as ("real" | "stress")[])("%s: rows × cols cells per panel", name => {
    const b = bundles[name];
    const desc = b.schema.inspectors.find(d => d.chart === "matrix")!;
    const p = b.inspect[desc.key] as MatrixPayload;
    render(desc, p);
    const panels = host.querySelectorAll(".mx");
    expect(panels).toHaveLength(p.panels.length);
    panels.forEach(panel => expect(panel.querySelectorAll(".mxg i")).toHaveLength(p.rows.length * p.cols.length));
  });
});

describe("ImageFigure", () => {
  const desc: InspectorDesc = {
    key: "maps",
    label: "Maps",
    chart: "image",
    options: [
      { key: "map", label: "Map", choices: [{ key: "mean", label: "Mean" }, { key: "std", label: "Spread" }] },
      { key: "scale", label: "Scale", choices: [{ key: "fixed", label: "Fixed" }, { key: "auto", label: "Auto" }] },
    ],
  };
  const payload: ImagePayload = { url: "/api/figure/maps?item=1.000000-P4 Gated 60.0A&map=mean", caption: "Regional map" };

  test("shows the image, caption and one segmented control per option", () => {
    render(desc, payload);
    expect(host.querySelector("figcaption")?.textContent).toBe("Regional map");
    expect(host.querySelectorAll(".seg")).toHaveLength(2);
    const src = new URL(host.querySelector("img")!.getAttribute("src")!, "http://h");
    expect(src.searchParams.get("map")).toBe("mean");
    expect(src.searchParams.get("scale")).toBe("fixed");
    expect(src.searchParams.get("item")).toBe("1.000000-P4 Gated 60.0A");
  });

  test("choosing an option refetches the image with that option in the query", () => {
    render(desc, payload);
    const spread = [...host.querySelectorAll("button")].find(b => b.textContent === "Spread")!;
    act(() => spread.click());
    const src = new URL(host.querySelector("img")!.getAttribute("src")!, "http://h");
    expect(src.pathname).toBe("/api/figure/maps");
    expect(src.searchParams.getAll("map")).toEqual(["std"]);
    expect(src.searchParams.get("scale")).toBe("fixed");
    expect(src.searchParams.get("item")).toBe("1.000000-P4 Gated 60.0A");
  });
});
