import { limitText } from "../contract/format";
import type { Schema } from "../contract/types";

interface Props {
  schema: Schema;
  axis: string;
  /** Label of the reference version (never its folder name). */
  reference: string;
  total: number;
}

const DASH = "–";

// Popover "How to read": guia do eixo e a tabela de métricas com limites (do esquema, nunca constantes) e repetibilidade.
export function HowToRead({ schema, axis, reference, total }: Props) {
  const axisLabel = new Map(schema.axes.map(a => [a.key, a.label]));
  const guide = schema.axes.find(a => a.key === axis)?.guide;
  return (
    <details className="how">
      <summary className="ui-chip how-chip">How to read</summary>
      <div className="panel">
        {guide ? <p className="how-guide">{guide}</p> : null}
        <div className="lrow lh">
          <span>Metric</span>
          <span>Review</span>
          <span>Reject</span>
          <span>Repeatability</span>
        </div>
        {schema.metrics.map(m => (
          <div className="lrow" key={m.key} title={m.description ?? undefined}>
            <span>
              {m.label} <span className="sub">· {axisLabel.get(m.axis) ?? m.axis}</span>
            </span>
            <span className="mono">{limitText(m, "review")}</span>
            <span className="mono">{limitText(m, "reject")}</span>
            <span className="mono">
              {typeof m.repeatability === "number" && Number.isFinite(m.repeatability)
                ? `${m.repeatability.toFixed(2)} ${m.unit}`.trim()
                : DASH}
            </span>
          </div>
        ))}
        <div className="src2 mono">
          Reference {reference} · {total} {schema.dataset.item.plural}
        </div>
      </div>
    </details>
  );
}
