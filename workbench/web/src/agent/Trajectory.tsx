import { useMemo } from "react";
import * as Observable from "@observablehq/plot";
import { Plot, type PlotOptions } from "../components/Plot";
import { OTHER, SERIES } from "../palette";
import { toHash } from "../route";
import { signedPercent, type Trajectory as Line } from "./experiments";
import { spreadValues } from "../components/labelSpread";

const GOAL = 15;
const HEIGHT = 190;
// margens verticais fixas: a altura da área de dados (para afastar os rótulos) depende delas
const MARGIN_TOP = 20;
const MARGIN_BOTTOM = 30;
const LABEL_GAP_PX = 14;
const RULE_INK = "#8f8c84";

interface Point {
  search: string;
  step: number;
  id: string;
  value: number;
}

interface Props {
  trajectories: Line[];
  // ordem das buscas (legenda do caderno): fixa a cor de cada série
  searches: string[];
  selected: string;
}

// Melhora ao longo da cadeia de cada busca; cada ponto é um link para o experimento (href no hash).
export function Trajectory({ trajectories, searches, selected }: Props) {
  const options = useMemo<PlotOptions | null>(() => {
    if (trajectories.length === 0) return null;
    const lines: Point[] = trajectories.flatMap(t =>
      t.ids.map((id, step) => ({ search: t.search, step, id, value: t.values[step] })),
    );
    const lastPoints = trajectories.map(t => lines.find(p => p.search === t.search && p.step === t.ids.length - 1)!);
    const current = lines.filter(p => p.id === selected);
    const top = Math.max(GOAL + 10, ...lines.map(p => p.value));
    // rótulos das pontas afastados em px (escala linear de 0 a top); os pontos ficam onde estão
    const plotHeight = HEIGHT - MARGIN_TOP - MARGIN_BOTTOM;
    const toPx = (v: number) => ((top - v) / top) * plotHeight;
    const fromPx = (p: number) => top - (p / plotHeight) * top;
    const labelYs = spreadValues(lastPoints.map(p => p.value), toPx, fromPx, LABEL_GAP_PX);
    const ends = lastPoints.map((p, i) => ({ ...p, labelY: labelYs[i] }));
    const longest = Math.max(...trajectories.map(t => t.ids.length));
    const link = (p: Point) => toHash({ view: "agent", exp: p.id });

    return {
      height: HEIGHT,
      marginTop: MARGIN_TOP,
      marginBottom: MARGIN_BOTTOM,
      marginLeft: 44,
      marginRight: 150,
      x: { domain: [0, Math.max(1, longest - 1)], axis: null },
      y: { domain: [0, top], label: null, tickFormat: (d: number) => `${d}%`, grid: true },
      color: { domain: searches, range: searches.map((_, i) => SERIES[i] ?? OTHER) },
      marks: [
        Observable.ruleY([GOAL], { stroke: RULE_INK, strokeDasharray: "4 4" }),
        Observable.text([GOAL], {
          x: Math.max(1, longest - 1),
          y: GOAL,
          text: () => "15% goal",
          dy: -7,
          textAnchor: "end",
          fill: RULE_INK,
          fontSize: 11,
        }),
        Observable.line(lines, { x: "step", y: "value", z: "search", stroke: "search", strokeWidth: 2 }),
        Observable.dot(lines, {
          x: "step",
          y: "value",
          stroke: "search",
          fill: "#fffefc",
          strokeWidth: 2,
          r: 4,
          href: link,
          title: (p: Point) => `${p.id} · ${signedPercent(p.value)}`,
        }),
        Observable.dot(current, {
          x: "step",
          y: "value",
          stroke: "search",
          fill: "search",
          strokeWidth: 2,
          r: 6,
          href: link,
        }),
        Observable.text(ends, {
          x: "step",
          y: "labelY",
          text: (p: Point) => `${p.search} · ${p.id}`,
          dx: 10,
          textAnchor: "start",
          fontSize: 11,
        }),
      ],
      style: { overflow: "visible", background: "transparent", color: "#16150f" },
    };
  }, [trajectories, searches, selected]);

  if (!options) return <p className="agent-empty">No numbers to plot yet.</p>;
  return <Plot options={options} fill className="traj-plot" aria-label="Trajectory" />;
}
