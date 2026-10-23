import { useState } from "react";
import { mapUrl } from "../api";

const LAYERS = [
  { id: "brilho", label: "Brightness" },
  { id: "fina", label: "Fine texture" },
  { id: "grossa", label: "Coarse texture" },
  { id: "veredito", label: "Texture verdict" },
] as const;

interface Props {
  caseId: string;
  maskOnly: boolean;
}

// Mapas por camada. O veredito só existe comparado com a original (o backend responde 400 sem isso).
export function RegionalTool({ caseId, maskOnly }: Props) {
  const [layer, setLayer] = useState<string>("brilho");
  const [compared, setCompared] = useState(false);
  const comparedOn = compared && !maskOnly;
  const shown = layer === "veredito" && !comparedOn ? "brilho" : layer;

  return (
    <div className="tool">
      <h3 className="tool-title">Regional</h3>
      <div className="tool-controls">
        <select value={shown} onChange={e => setLayer(e.target.value)} aria-label="Layer">
          {LAYERS.map(item => (
            <option key={item.id} value={item.id} disabled={item.id === "veredito" && !comparedOn}>
              {item.label}
            </option>
          ))}
        </select>
        <label>
          <input
            type="checkbox"
            checked={comparedOn}
            disabled={maskOnly}
            onChange={e => {
              setCompared(e.target.checked);
              if (!e.target.checked && layer === "veredito") setLayer("brilho");
            }}
          />
          Compared with original
        </label>
      </div>
      <img className="tool-map" src={mapUrl(caseId, shown, comparedOn)} alt={shown} />
    </div>
  );
}
