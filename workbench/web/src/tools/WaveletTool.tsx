import { useMemo } from "react";
import * as Observable from "@observablehq/plot";
import type { WaveletBands } from "../api";
import { Info } from "../components/Info";
import { waveletType } from "../definitions";
import { Plot, type PlotOptions } from "../components/Plot";
import { num } from "../format";
import { GRID, REFERENCE_INK, SERIES } from "../palette";
import { useToolData } from "./toolData";

const WIDTH = 640;

interface Props {
  version: string;
  caseId: string;
}

export function WaveletTool({ version, caseId }: Props) {
  const { data, error } = useToolData<WaveletBands>("wavelet", version, caseId);

  const options = useMemo<PlotOptions | null>(() => {
    if (!data) return null;
    // log2_ratio nulo não entra no gráfico.
    const bars = data.bands
      .filter(b => typeof b.log2_ratio === "number" && Number.isFinite(b.log2_ratio))
      .map(b => ({ ...b, t: `${num(b.log2_ratio, 3)} · ${b.band}` }));
    return {
      width: WIDTH,
      height: 300,
      marginLeft: 56,
      fx: { label: null },
      x: { label: null },
      // Uma única série: uma cor só para todas as barras.
      y: { label: null },
      marks: [
        Observable.gridY({ stroke: GRID }),
        Observable.ruleY([0], { stroke: REFERENCE_INK }),
        Observable.barY(bars, {
          fx: "level",
          x: "band",
          y: "log2_ratio",
          fill: SERIES[0],
          title: "t",
          tip: true,
        }),
      ],
    };
  }, [data]);

  return (
    <div className="tool">
      <h3 className="tool-title">
        Wavelet <Info term="wavelet_fine" />
      </h3>
      {error && <p className="tool-error">{error}</p>}
      {data && (
        <>
          <p className="tool-label">Type: {waveletType(data.type)}</p>
          {options && <Plot options={options} />}
        </>
      )}
    </div>
  );
}
