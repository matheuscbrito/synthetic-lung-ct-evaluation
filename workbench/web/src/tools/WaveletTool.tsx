import { useMemo } from "react";
import * as Observable from "@observablehq/plot";
import type { WaveletBands } from "../api";
import { Info } from "../components/Info";
import { Plot, type PlotOptions } from "../components/Plot";
import { useToolData } from "./toolData";

const WIDTH = 640;

// Tipo do wavelet vem do backend em português; a interface mostra em inglês (valor cru se desconhecido).
const TYPE_LABEL: Record<string, string> = {
  borrou: "blurred",
  "ruído": "noise",
  "perdeu contraste": "lost contrast",
  "textura preservada": "texture preserved",
};

interface Props {
  version: string;
  caseId: string;
}

export function WaveletTool({ version, caseId }: Props) {
  const { data, error } = useToolData<WaveletBands>("wavelet", version, caseId);

  const options = useMemo<PlotOptions | null>(() => {
    if (!data) return null;
    // log2_ratio nulo não entra no gráfico.
    const bars = data.bands.filter(b => typeof b.log2_ratio === "number" && Number.isFinite(b.log2_ratio));
    return {
      width: WIDTH,
      height: 300,
      marginLeft: 56,
      fx: { label: null },
      x: { label: null },
      y: { label: null, grid: true },
      marks: [
        Observable.ruleY([0], { stroke: "#333" }),
        Observable.barY(bars, {
          fx: "level",
          x: "band",
          y: "log2_ratio",
          fill: "#7a8a84",
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
          <p className="tool-label">Type: {TYPE_LABEL[data.type] ?? data.type}</p>
          {options && <Plot options={options} />}
        </>
      )}
    </div>
  );
}
