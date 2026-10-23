import type { NotebookRow } from "../api";
import { SERIES } from "../palette";
import { lineage, signedPercent, verdictTint } from "./experiments";

interface Metric {
  name: string;
  best: string;
  other: string;
}

interface Props {
  rows: NotebookRow[];
  metrics: Metric[];
  id: string;
  onSelect: (id: string) => void;
}

// Escala das barras de melhora: 25% no mínimo, ou o maior valor exibido.
const BAR_MAX_PX = 60;
const SCOPE_LABELS = ["5", "10", "37"];

// Detalhe de um experimento: título, linhagem clicável, barras por escopo e o cartão de mudança ou de métricas.
export function ExperimentDetail({ rows, metrics, id, onSelect }: Props) {
  const row = rows.find(r => r.id === id);
  if (!row) return null;
  const [bg, fg] = verdictTint(row.verdict);
  const chain = lineage(rows, id);
  const labelOf = (i: number) => (row.vals.length === 3 ? SCOPE_LABELS[i] : row.scope ?? "—");
  const top = Math.max(25, ...row.vals.map(v => Math.abs(v)));

  return (
    <section className="xdetail" aria-label="Experiment detail">
      <div className="xhead">
        <h2>
          {row.id} · {row.change}
        </h2>
        <span className="xpill" style={{ background: bg, color: fg }}>
          {row.verdict}
        </span>
        {row.best && <span className="xtag">Current best</span>}
      </div>

      <nav className="lineage" aria-label="Lineage">
        <span className="ln ln-static">baseline</span>
        {chain.map(x => (
          <span key={x} className="lineage-step">
            <span aria-hidden="true">›</span>
            {x === id ? (
              <span className="ln cur" aria-current="step">
                {x}
              </span>
            ) : (
              <button type="button" className="ln" onClick={() => onSelect(x)}>
                {x}
              </button>
            )}
          </span>
        ))}
      </nav>

      <div className="xcards">
        <div className="card">
          <div className="eyebrow ink">Improvement vs baseline</div>
          {row.vals.length > 0 ? (
            <div className="scopes">
              {row.vals.map((v, i) => (
                <div className="scope" key={i}>
                  <b className="mono">{signedPercent(v)}</b>
                  <i style={{ height: Math.max(4, (Math.abs(v) / top) * BAR_MAX_PX), background: SERIES[0] }} />
                  <span>{labelOf(i) === "—" ? "—" : `${labelOf(i)} slices`}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="reason">{row.gain_text}</div>
          )}
          {row.reason && <div className="reason">{row.reason}</div>}
        </div>

        {row.best && metrics.length > 0 ? (
          <div className="card">
            <div className="eyebrow ink">Per-metric improvement · 37 slices</div>
            {metrics.map(m => (
              <div className="metric-row" key={m.name}>
                <span>{m.name}</span>
                <b className="mono">{m.best}</b>
                <span className="sub mono">{m.other}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="card">
            <div className="eyebrow ink">Change</div>
            <div className="change-text">{row.change}</div>
            <div className="reason">Base: {row.base}</div>
          </div>
        )}
      </div>
    </section>
  );
}
