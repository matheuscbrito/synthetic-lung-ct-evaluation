import { useMemo } from "react";
import type { Slice, Verdict } from "../api";
import { COLOR } from "../status";
import { num } from "../format";
import { Plot, type PlotOptions } from "./Plot";
import * as Observable from "@observablehq/plot";

interface Props {
  slices: Slice[];
  verdict: Verdict;
  hovered: string | null;
}

const GREEN = "#e3f4ea"; // |z| ≤ 1
const YELLOW = "#fbf1d2"; // 1 < |z| ≤ 2
const RED = "#f6dcd8"; // |z| > 2

// Uma faixa horizontal por métrica com z em algum tile; um ponto por tile.
export function ZStrip({ slices, verdict, hovered }: Props) {
  const options = useMemo<PlotOptions | null>(() => {
    const labels = new Map<string, string>();
    const points: { row: string; z: number; id: string; color: string; r: number; title: string }[] = [];
    for (const slice of slices) {
      for (const metric of slice.metrics) {
        if (metric.group !== verdict || metric.z === null) continue;
        if (!labels.has(metric.key)) labels.set(metric.key, metric.label);
        points.push({
          row: metric.key,
          z: metric.z,
          id: slice.case_id,
          color: COLOR[metric.status],
          r: hovered === slice.case_id ? 7 : 4,
          title: `${slice.label} · z ${num(metric.z)}`,
        });
      }
    }
    if (labels.size === 0) return null;

    const zs = points.map(p => p.z);
    const lo = Math.min(-3, ...zs);
    const hi = Math.max(3, ...zs);
    const bands = [
      { x1: lo, x2: -2, fill: RED },
      { x1: -2, x2: -1, fill: YELLOW },
      { x1: -1, x2: 1, fill: GREEN },
      { x1: 1, x2: 2, fill: YELLOW },
      { x1: 2, x2: hi, fill: RED },
    ];
    const rows = [...labels.keys()];
    const bandRows = rows.flatMap(row => bands.map(b => ({ ...b, row })));

    return {
      width: 300,
      height: rows.length * 22 + 28,
      marginLeft: 150,
      marginRight: 8,
      marginTop: 4,
      marginBottom: 20,
      x: { domain: [lo, hi], label: "z" },
      y: { domain: rows, tickFormat: key => labels.get(key) ?? key, label: null },
      color: { type: "identity" },
      marks: [
        Observable.rectX(bandRows, { x1: "x1", x2: "x2", y: "row", fill: "fill" }),
        Observable.ruleX([0], { stroke: "#8a938f" }),
        Observable.dot(points, {
          x: "z",
          y: "row",
          fill: "color",
          r: "r",
          stroke: "#fcfcfb",
          strokeWidth: 2,
          title: "title",
          tip: true,
        }),
      ],
    };
  }, [slices, verdict, hovered]);

  if (!options) return null;
  return <Plot className="zstrip" options={options} />;
}
