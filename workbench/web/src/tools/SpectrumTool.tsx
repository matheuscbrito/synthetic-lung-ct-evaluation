import { useMemo } from "react";
import type { Spectrum } from "../api";
import { Info } from "../components/Info";
import { Plot, type PlotOptions } from "../components/Plot";
import { spectrumMarks } from "../components/spectrumMarks";
import { REFERENCE_INK, SERIES } from "../palette";
import { useToolData } from "./toolData";
import { spectrumSeries } from "./series";

const WIDTH = 640;
const LABELS: Record<string, string> = { real: "Real", synthetic: "Synthetic" };

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
      marginRight: 84,
      x: { domain: [0, data.nyquist], label: null },
      y: { type: "log", label: null },
      // Real em neutro de referência; sintético na primeira cor da série.
      color: {
        domain: ["real", "synthetic"],
        range: [REFERENCE_INK, SERIES[0]],
        legend: true,
      },
      marks: spectrumMarks({
        band,
        nyquist: data.nyquist,
        top,
        lines: lines.map(p => ({ f: p.f, power: p.power, key: p.which })),
        direct: true,
        labelOf: key => LABELS[key] ?? key,
      }),
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
