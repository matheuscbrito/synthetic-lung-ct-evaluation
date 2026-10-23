import type { Metric, Status } from "../api";
import { num } from "../format";
import { calcLines } from "./calc";

interface Props {
  metric: Metric;
}

// Tinta do texto por status (pílulas do deck); a cor do ponto continua vindo de status.ts.
const INK: Record<Status, string> = {
  approved: "#1f7a43",
  review: "#9a6408",
  rejected: "#a83224",
  inconclusive: "#6b6b66",
};

// Cálculo de uma métrica: valores real e sintético, fórmula com o resultado e a regra de status.
export function CalcBox({ metric }: Props) {
  const lines = calcLines(metric);
  return (
    <div className="calc">
      <div className="eyebrow">Calculation</div>
      <div className="crow">
        <span>Real</span>
        <span className="mono">{num(metric.real, 3)}</span>
      </div>
      <div className="crow">
        <span>Synthetic</span>
        <span className="mono">{num(metric.synthetic, 3)}</span>
      </div>
      {lines.result !== null && (
        <div className="formula mono">
          <span>{lines.formula ?? "Value"}</span>
          <b style={{ color: INK[metric.status] }}>{lines.result}</b>
        </div>
      )}
      {lines.rule !== "" && <div className="src2 mono">{lines.rule}</div>}
    </div>
  );
}
