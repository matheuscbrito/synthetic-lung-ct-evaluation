import { useMemo } from "react";
import * as Observable from "@observablehq/plot";
import type { Spectrum } from "../api";
import { Info } from "../components/Info";
import { Plot, type PlotOptions } from "../components/Plot";
import { useToolData } from "./toolData";
import { spectrumSeries } from "./series";

const REAL = "#333";
const SYNTHETIC = "#e45756";
const WIDTH = 640;

interface Props {
  version: string;
  caseId: string;
}

export function SpectrumTool({ version, caseId }: Props) {
  const { data, error } = useToolData<Spectrum>("spectrum", version, caseId);

  const options = useMemo<PlotOptions | null>(() => {
    if (!data) return null;
    const { band, lines } = spectrumSeries(data);
    const top = Math.max(0, ...lines.map(p => p.power), ...band.map(p => p.hi));
    return {
      width: WIDTH,
      height: 320,
      marginLeft: 56,
      x: { domain: [0, data.nyquist], label: null },
      y: { type: "log", label: null },
      color: { domain: ["real", "synthetic"], range: [REAL, SYNTHETIC], legend: true },
      marks: [
        Observable.areaY(band, { x: "f", y1: "lo", y2: "hi", fill: "#9aa3a0", fillOpacity: 0.35 }),
        Observable.ruleX([data.nyquist], { stroke: "#999", strokeDasharray: "4 3" }),
        Observable.text([{ f: data.nyquist, p: top, label: "Nyquist" }], {
          x: "f",
          y: "p",
          text: "label",
          textAnchor: "end",
          dx: -4,
          dy: 10,
        }),
        Observable.line(lines, { x: "f", y: "power", stroke: "which", z: "which", strokeWidth: 1.5 }),
      ],
    };
  }, [data]);

  return (
    <div className="tool">
      <h3 className="tool-title">
        Spectrum <Info term="spectrum" />
      </h3>
      {error && <p className="tool-error">{error}</p>}
      {options && <Plot options={options} />}
    </div>
  );
}
