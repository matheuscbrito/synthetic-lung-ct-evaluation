// Gráficos de coorte da visão geral: uma faixa por métrica do eixo (faixas de status, limites tracejados,
// barras de IC, item em foco ampliado, clique abre o item) e um real × sintético por métrica que tem as
// duas leituras (linha identidade, escala Auto/×½/×¼). Com uma versão para comparar, os mesmos gráficos
// dela vêm logo abaixo, no mesmo domínio e na mesma ordem (paridade #19–21, 30–35, 47, 49, 73, 81).
import { useState } from "react";
import { STATUS_DOT, STATUS_FILL, fmt } from "../charts/num";
import { metricText, ticks } from "../contract/format";
import type { Item, MetricDesc, Schema } from "../contract/types";
import { Seg } from "../ui/Seg";
import { alignTo, cohortSeries, hasScatter, scatterSeries } from "./cohort";
import type { CompareVersion } from "./VerdictMatrix";

interface Props {
  schema: Schema;
  axis: string;
  items: Item[];
  onOpen: (id: string) => void;
  focus?: string;
  technique?: string;
  scatterFirst?: boolean;
  /** Label of the version shown in `items` (used when a compare version is stacked). */
  label?: string;
  compare?: CompareVersion | null;
}

interface Panel {
  label?: string;
  items: Item[];
}

const W = 720;
const H = 150;
const PL = 46, PR = 10, PT = 8, PB = 18;

function StripChart({ schema, metric, panel, other, focus, onOpen }: {
  schema: Schema;
  metric: MetricDesc;
  panel: Panel;
  other?: Item[];
  focus?: string;
  onOpen: (id: string) => void;
}) {
  const s = cohortSeries(panel.items, metric, schema, other);
  const [lo, hi] = s.domain;
  const n = Math.max(1, panel.items.length);
  const X = (i: number) => PL + ((i + 0.5) / n) * (W - PL - PR);
  const Y = (v: number) => PT + (1 - (Math.min(hi, Math.max(lo, v)) - lo) / (hi - lo || 1)) * (H - PT - PB);
  const rules = [...new Set(s.bands.flatMap(b => [b.from, b.to]))].filter(v => v > lo && v < hi);
  const yTicks = ticks(lo, hi, 4).filter(v => v >= lo && v <= hi);
  const r = n > 60 ? 2.6 : 3.6;
  const byId = new Map(panel.items.map(it => [it.id, it]));
  return (
    <div className="cohort-panel">
      {panel.label && <div className="eyebrow">{panel.label}</div>}
      <svg className="spec cohort-strip" viewBox={`0 0 ${W} ${H}`}>
        <title>{`${metric.label} by ${schema.dataset.item.singular}`}</title>
        {s.bands.map((b, i) => (
          <rect key={i} className="cband" data-status={b.status} x={PL} width={W - PL - PR}
            y={Y(b.to)} height={Math.max(0, Y(b.from) - Y(b.to))} fill={STATUS_FILL[b.status]} />
        ))}
        {yTicks.map(v => (
          <text key={v} x={PL - 6} y={Y(v) + 3} className="ax" textAnchor="end">{fmt(v)}</text>
        ))}
        {lo < 0 && hi > 0 && <line className="zero" x1={PL} x2={W - PR} y1={Y(0)} y2={Y(0)} />}
        {rules.map(v => (
          <line key={v} className="rule" x1={PL} x2={W - PR} y1={Y(v)} y2={Y(v)} />
        ))}
        {s.points.map(p =>
          p.lo !== null && p.hi !== null ? (
            <line key={`ci-${p.id}`} className="cbar" x1={X(p.index)} x2={X(p.index)} y1={Y(p.lo)} y2={Y(p.hi)} />
          ) : null,
        )}
        {s.points.map(p => {
          const it = byId.get(p.id)!;
          const focused = p.id === focus;
          return (
            <circle key={p.id} className={focused ? "pt focus" : "pt"} data-id={p.id} data-status={p.status}
              cx={X(p.index)} cy={Y(p.y)} r={focused ? r * 2 : r} fill={STATUS_DOT[p.status]}
              onClick={() => onOpen(p.id)}>
              <title>{[it.label, metricText(metric, it.metrics[metric.key]), it.metrics[metric.key]?.note].filter(Boolean).join(" · ")}</title>
            </circle>
          );
        })}
      </svg>
      <div className="cohort-cap">
        {`${s.points.length} of ${panel.items.length} read`}
        {s.points.length < panel.items.length ? " · items without a reading are left out, order kept" : ""}
      </div>
    </div>
  );
}

const SCALES = [
  { value: "1", label: "Auto" },
  { value: "0.5", label: "×½" },
  { value: "0.25", label: "×¼" },
];

const S = 240;
const SP = 34;

function ScatterChart({ schema, metric, panel, other, scale, focus, onOpen }: {
  schema: Schema;
  metric: MetricDesc;
  panel: Panel;
  other?: Item[];
  scale: number;
  focus?: string;
  onOpen: (id: string) => void;
}) {
  const s = scatterSeries(panel.items, metric, other);
  const span = s.max - s.min || Math.abs(s.max) || 1;
  const lo = s.min - span * 0.05;
  const hi = lo + (s.max + span * 0.05 - lo) * scale;
  const inside = s.points.filter(p => p.x <= hi && p.y <= hi);
  const P = (v: number) => SP + ((v - lo) / (hi - lo || 1)) * (S - SP - 8);
  const Yp = (v: number) => S - P(v);
  const t = ticks(lo, hi, 3).filter(v => v >= lo && v <= hi);
  const byId = new Map(panel.items.map(it => [it.id, it]));
  return (
    <div className="cohort-panel">
      {panel.label && <div className="eyebrow">{panel.label}</div>}
      <svg className="spec cohort-scatter" viewBox={`0 0 ${S} ${S}`} style={{ height: S, width: S }}>
        <title>{`${metric.label}: real against synthetic`}</title>
        <line className="ident" x1={P(lo)} y1={Yp(lo)} x2={P(hi)} y2={Yp(hi)} />
        {t.map(v => (
          <g key={v}>
            <text x={P(v)} y={S - SP + 14} className="ax" textAnchor="middle">{fmt(v)}</text>
            <text x={SP - 4} y={Yp(v) + 3} className="ax" textAnchor="end">{fmt(v)}</text>
          </g>
        ))}
        <text x={(SP + S) / 2} y={S - 2} className="ax" textAnchor="middle">real</text>
        <text x={8} y={(S - SP) / 2} className="ax" textAnchor="middle" transform={`rotate(-90 8 ${(S - SP) / 2})`}>
          synthetic
        </text>
        {inside.map(p => {
          const focused = p.id === focus;
          return (
            <circle key={p.id} className={focused ? "pt focus" : "pt"} data-id={p.id} data-status={p.status}
              cx={P(p.x)} cy={Yp(p.y)} r={focused ? 6 : 3.6} fill={STATUS_DOT[p.status]} onClick={() => onOpen(p.id)}>
              <title>{[byId.get(p.id)!.label, `real ${fmt(p.x)}`, `synthetic ${fmt(p.y)}`, schema.statuses.find(s => s.key === p.status)?.label ?? p.status,
                byId.get(p.id)!.metrics[metric.key]?.note].filter(Boolean).join(" · ")}</title>
            </circle>
          );
        })}
      </svg>
      <div className="cohort-cap">
        {`${s.points.length} of ${panel.items.length} with both readings`}
        {inside.length < s.points.length ? ` · ${s.points.length - inside.length} outside this scale` : ""}
      </div>
    </div>
  );
}

function ScatterBlock({ schema, metric, panels, focus, onOpen }: {
  schema: Schema;
  metric: MetricDesc;
  panels: Panel[];
  focus?: string;
  onOpen: (id: string) => void;
}) {
  const [scale, setScale] = useState("1");
  return (
    <section className="cohort-card cohort-sc">
      <header>
        <h3>{metric.label}</h3>
        <Seg small label={`Scale of ${metric.label}`} value={scale} onChange={setScale} options={SCALES} />
      </header>
      <div className="chart-status-legend" aria-label="Point assessment"><span>Color: {schema.axes.find(a => a.key === metric.axis)?.label ?? metric.axis} verdict</span>{schema.statuses.map(s => <span key={s.key}><i style={{ background: STATUS_DOT[s.key] }} aria-hidden="true" />{s.label}</span>)}</div>
      <div className="cohort-pair">
        {panels.map((p, i) => (
          <ScatterChart key={i} schema={schema} metric={metric} panel={p} scale={Number(scale)} focus={focus} onOpen={onOpen}
            other={panels.length > 1 ? panels[1 - i].items : undefined} />
        ))}
      </div>
    </section>
  );
}

export function CohortCharts({ schema, axis, items, onOpen, focus, label, compare, technique, scatterFirst = false }: Props) {
  const metrics = schema.metrics.filter(m => m.axis === axis && (!technique || m.technique === technique));
  const panels: Panel[] = compare
    ? [{ label: label ?? "This version", items }, { label: compare.label, items: alignTo(items, compare.items) }]
    : [{ items }];
  const scatter = metrics.filter(m => panels.some(p => hasScatter(p.items, m)));
  const strips = (
      <div className="cohort-strips">
        {metrics.map(m => (
          <section key={m.key} className="cohort-card">
            <header>
              <h3>{m.label}</h3>
              <span className="sub">{m.display === "z" ? `z (${m.unit})` : m.unit}</span>
            </header>
            {m.description && <details className="cohort-help"><summary>How to read this chart</summary><p className="cohort-desc">{m.description}</p></details>}
            {panels.map((p, i) => (
              <StripChart key={i} schema={schema} metric={m} panel={p} focus={focus} onOpen={onOpen}
                other={panels.length > 1 ? panels[1 - i].items : undefined} />
            ))}
          </section>
        ))}
      </div>
  );
  const comparisons = scatter.length > 0 ? (
        <>
          <div className="eyebrow cohort-h">Real against synthetic</div>
          <div className="cohort-scatters">
            {scatter.map(m => (
              <ScatterBlock key={m.key} schema={schema} metric={m} panels={panels} focus={focus} onOpen={onOpen} />
            ))}
          </div>
        </>
      ) : null;
  return <div className="cohort">{scatterFirst ? <>{comparisons}<details className="inspector-charts"><summary>Deviation from original · details</summary>{strips}</details></> : <>{strips}{comparisons}</>}</div>;
}
