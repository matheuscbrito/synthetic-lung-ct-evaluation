import type { Metric, Slice, Status, Verdict } from "../api";
import { DEFINITIONS, type Term } from "../definitions";
import { COLOR } from "../status";
import { num } from "../format";
import { Info } from "./Info";

interface Props {
  slice: Slice;
}

function isTerm(key: string): key is Term {
  return key in DEFINITIONS;
}

function Dot({ status }: { status: Status }) {
  return <span className="dot" title={status} style={{ background: COLOR[status] }} />;
}

// z em IQR com sinal; métrica sem z mostra o valor bruto.
function metricValue(metric: Metric): string {
  if (metric.z !== null && Number.isFinite(metric.z)) {
    return `${metric.z >= 0 ? "+" : ""}${num(metric.z, 1)} IQR`;
  }
  return num(metric.value);
}

// Linhas de métrica de um grupo; reaproveitada pela comparação de cortes.
export function MetricList({ metrics }: { metrics: Metric[] }) {
  return (
    <ul className="metrics">
      {metrics.map(metric => (
        <li key={metric.key}>
          {metric.label}
          {isTerm(metric.key) && <Info term={metric.key} />}
          {" · "}
          {metricValue(metric)}
          {" · "}
          <Dot status={metric.status} />
        </li>
      ))}
    </ul>
  );
}

function Block({ slice, verdict, title }: { slice: Slice; verdict: Verdict; title: string }) {
  const block = slice[verdict];
  const metrics = slice.metrics.filter(m => m.group === verdict);
  return (
    <section className="verdict-block">
      <h3>
        {title} <Info term={verdict} />
      </h3>
      <div className="verdict-pill" style={{ borderColor: COLOR[block.verdict] }}>{block.verdict}</div>
      <ul className="techniques">
        {Object.entries(block.techniques).map(([name, status]) => (
          <li key={name}>
            <Dot status={status} /> {name}
          </li>
        ))}
      </ul>
      <MetricList metrics={metrics} />
    </section>
  );
}

export function VerdictPanel({ slice }: Props) {
  return (
    <aside className="verdict-panel">
      <Block slice={slice} verdict="brightness" title="Brightness" />
      <Block slice={slice} verdict="texture" title="Texture" />
      <footer>
        <div>{`Density: ${slice.density.status} (${num(slice.density.median_shift_iqr)} IQR)`}</div>
        <div>{`Wavelet type: ${slice.wavelet_type}`}</div>
      </footer>
    </aside>
  );
}
