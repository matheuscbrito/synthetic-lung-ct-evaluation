import { Fragment, useState } from "react";
import type { Metric, Slice, Status, Verdict } from "../api";
import { DEFINITIONS, waveletType, type Term } from "../definitions";
import { COLOR } from "../status";
import { num } from "../format";
import { Info } from "./Info";
import { Pill } from "../ui/Pill";
import { CalcBox } from "./CalcBox";

interface Props {
  slice: Slice;
}

function isTerm(key: string): key is Term {
  return key in DEFINITIONS;
}

function Dot({ status }: { status: Status }) {
  return <span className="dot" title={status} style={{ background: COLOR[status] }} />;
}

function titleCase(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// Número com sinal e unidade; null vira "–".
function signed(x: number | null): string {
  if (x === null || !Number.isFinite(x)) return "–";
  return `${x >= 0 ? "+" : ""}${x.toFixed(2)}`;
}

// Valor da linha: z em IQR, sat31 em %, demais valores brutos.
function rowValue(metric: Metric): string {
  if (metric.z !== null && Number.isFinite(metric.z)) return `${signed(metric.z)} IQR`;
  if (metric.key === "sat31") return metric.value === null ? "–" : `${num(metric.value, 1)}%`;
  return num(metric.value, 3);
}

// z em IQR com sinal; métrica sem z mostra o valor bruto. Usada pela comparação de cortes.
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
          <span className="m-name">
            {metric.label}
            {isTerm(metric.key) && <Info term={metric.key} />}
          </span>
          <span className="m-val">{metricValue(metric)}</span>
          <Dot status={metric.status} />
        </li>
      ))}
    </ul>
  );
}

interface RowsProps {
  metrics: Metric[];
  openKey: string | null;
  onToggle: (key: string) => void;
}

// Uma linha por métrica; a linha aberta mostra o cálculo logo abaixo.
function MetricRows({ metrics, openKey, onToggle }: RowsProps) {
  return (
    <>
      {metrics.map(metric => {
        const key = `${metric.group}:${metric.key}`;
        const open = openKey === key;
        return (
          <Fragment key={key}>
            <button
              type="button"
              className={open ? "mrow open" : "mrow"}
              aria-expanded={open}
              onClick={() => onToggle(key)}
            >
              <span>
                {metric.label}
                {isTerm(metric.key) && <Info term={metric.key} />}
              </span>
              <span className="mono">{rowValue(metric)}</span>
              <Dot status={metric.status} />
            </button>
            {open && <CalcBox metric={metric} />}
          </Fragment>
        );
      })}
    </>
  );
}

function Column({ slice, verdict }: { slice: Slice; verdict: Verdict }) {
  const block = slice[verdict];
  return (
    <div>
      <div className="eyebrow">{verdict === "texture" ? "Texture" : "Brightness"}</div>
      <Pill status={block.verdict} label={titleCase(block.verdict)} />
      <div className="techs">
        {Object.entries(block.techniques).map(([name, status]) => (
          <span key={name}>
            <i className="dot" style={{ background: COLOR[status] }} />
            {name}
          </span>
        ))}
      </div>
    </div>
  );
}

// Veredito do corte: pílulas de Texture e Brightness, métricas por grupo e cálculo de uma linha por vez.
export function VerdictPanel({ slice }: Props) {
  // um cálculo aberto por vez, em qualquer grupo; troca de corte fecha tudo
  const [openKey, setOpenKey] = useState<string | null>(null);
  const toggle = (key: string) => setOpenKey(current => (current === key ? null : key));

  return (
    <aside className="verdict">
      <div className="vhead">
        <Column slice={slice} verdict="texture" />
        <Column slice={slice} verdict="brightness" />
      </div>
      <div className="eyebrow green">Texture metrics</div>
      <MetricRows metrics={slice.metrics.filter(m => m.group === "texture")} openKey={openKey} onToggle={toggle} />
      <div className="eyebrow red">Brightness metrics</div>
      <MetricRows metrics={slice.metrics.filter(m => m.group === "brightness")} openKey={openKey} onToggle={toggle} />
      <div className="foot">
        <div>{`Density · ${slice.density.status} (${signed(slice.density.median_shift_iqr)} IQR)`}</div>
        <div>{`Wavelet type · ${waveletType(slice.wavelet_type)}`}</div>
      </div>
    </aside>
  );
}
