// Generators › Notebook (slide "Notebook" dos mockups v3, docs/planning/mockups-v3/render_v3.py `slide_exp`):
// lista única de experimentos com busca, detalhe com linhagem e placar por escopo, tabela quando existe,
// trajetória com a meta e cartão de seções. Textos do notebook passam sem alteração; a interface é em inglês.
import { useState } from "react";
import { useContract } from "../contract/client";
import { signed, toneOf } from "../contract/format";
import type { Experiment, Experiments, Schema } from "../contract/types";
import { TONE_COLORS } from "../dataset/strip";
import type { Route } from "../route";
import { PageHeader } from "../ui/PageHeader";
import { GeneratorTabs } from "./GeneratorTabs";
import {
  filterExperiments,
  lastScore,
  lineage,
  selectedId,
  trajectoryLayout,
  trajectoryPaths,
  type ChartBox,
} from "./notebook";
import "./notebook.css";

const BOX: ChartBox = { width: 560, height: 190, left: 40, right: 60, top: 12, bottom: 26 };
/** Trajectory series colours: the best lineage, then the latest experiment outside it. */
const SERIES = ["#2a78d6", "#eb6834"];

interface PageProps {
  route: Route;
  onRoute: (patch: Partial<Route>) => void;
}

/** Score text with the objective unit (`%` attached, other units spaced); `n/a` when there is no reading. */
export function scoreText(value: number | null, unit: string): string {
  if (value === null) return "n/a";
  const suffix = unit === "%" ? "%" : unit ? ` ${unit}` : "";
  return `${signed(value, 1)}${suffix}`;
}

function Message({ text, error }: { text: string; error?: boolean }) {
  return <p className={error ? "error" : "sub"}>{text}</p>;
}

/** Notebook wired to the API: one fetch of `/api/experiments` for the current dataset. */
export function GeneratorNotebook({ schema, route, onRoute }: { schema: Schema } & PageProps) {
  const notebook = useContract<Experiments>("/api/experiments", { dataset: schema.dataset.key });
  if (notebook.error) return <Message error text={notebook.error} />;
  if (!notebook.data) return <Message text="Loading…" />;
  if (notebook.data.experiments.length === 0) return <Message text="No experiments yet." />;
  return <Notebook schema={schema} data={notebook.data} route={route} onRoute={onRoute} />;
}

function Notebook({ schema, data, route, onRoute }: { schema: Schema; data: Experiments } & PageProps) {
  const [query, setQuery] = useState("");
  const { experiments, scopes, objective } = data;
  const byId = new Map(experiments.map(e => [e.id, e]));
  const current = selectedId(experiments, route.exp);
  const exp = current === null ? undefined : byId.get(current);
  const shown = filterExperiments(experiments, query);

  return (
    <div className="nb">
      <PageHeader
        eyebrow="Generators · optimizers"
        title="Notebook"
        sub={`Experiments, lessons and next steps · source ${data.source.label}`}
        right={<GeneratorTabs active="exp" addons={schema.addons} onSelect={tab => onRoute({ tab })} />}
      />
      <div className="nb-body">
        <aside className="card nb-list">
          <input
            className="nb-search"
            type="search"
            placeholder="Filter experiments"
            aria-label="Filter experiments"
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
          <div className="eyebrow nb-count">Experiments · {experiments.length}</div>
          {shown.length === 0 && <p className="sub">No experiment matches.</p>}
          {shown.map(e => (
            <ListItem
              key={e.id}
              exp={e}
              schema={schema}
              scopes={scopes}
              unit={objective.unit}
              on={e.id === current}
              onPick={() => onRoute({ exp: e.id })}
            />
          ))}
        </aside>
        <div className="nb-main">
          {exp && <Detail schema={schema} data={data} exp={exp} byId={byId} onRoute={onRoute} />}
          <div className="nb-grid">
            <Trajectory data={data} selected={current} onRoute={onRoute} />
            <SectionsCard data={data} />
          </div>
        </div>
      </div>
    </div>
  );
}

function ListItem({
  exp,
  schema,
  scopes,
  unit,
  on,
  onPick,
}: {
  exp: Experiment;
  schema: Schema;
  scopes: Experiments["scopes"];
  unit: string;
  on: boolean;
  onPick: () => void;
}) {
  const tone = TONE_COLORS[toneOf(schema, exp.outcome.status)];
  return (
    <button type="button" className={on ? "nb-item on" : "nb-item"} aria-pressed={on} onClick={onPick}>
      <span className="nb-id mono">{exp.id}</span>
      <span className="nb-change">{exp.change}</span>
      <span className="nb-chip mono" style={{ background: tone.bg, color: tone.fg }}>
        {scoreText(lastScore(exp, scopes), unit)}
      </span>
      {exp.is_best && (
        <i className="nb-best" aria-label="Current best">
          ★
        </i>
      )}
    </button>
  );
}

function Detail({
  schema,
  data,
  exp,
  byId,
  onRoute,
}: {
  schema: Schema;
  data: Experiments;
  exp: Experiment;
  byId: Map<string, Experiment>;
  onRoute: (patch: Partial<Route>) => void;
}) {
  const tone = TONE_COLORS[toneOf(schema, exp.outcome.status)];
  const table = data.tables.find(t => t.for === exp.id);
  const scored = data.scopes.flatMap(s => {
    const v = exp.scores[s.key];
    return typeof v === "number" && Number.isFinite(v) ? [{ label: s.label, value: v }] : [];
  });
  const max = Math.max(1, ...scored.map(s => Math.abs(s.value)));
  return (
    <section className="nb-detail">
      <div className="nb-head">
        <h2>
          {exp.id} · {exp.change}
        </h2>
        <span className="nb-pill" style={{ background: tone.bg, color: tone.fg }}>
          <i style={{ background: tone.mark }} aria-hidden="true" />
          {exp.outcome.label}
        </span>
        {exp.is_best && <span className="nb-tag">Current best</span>}
      </div>
      <div className="nb-lineage">
        {lineage(byId, exp.id).map((id, i) => (
          <span key={id} className="nb-step">
            {i > 0 && <span className="nb-sep">›</span>}
            <button type="button" className={id === exp.id ? "nb-ln cur" : "nb-ln"} onClick={() => onRoute({ exp: id })}>
              {id}
            </button>
          </span>
        ))}
      </div>
      <div className="nb-cards">
        <div className="card">
          <div className="eyebrow ink">{data.objective.label} by scope</div>
          <div className="nb-scopes">
            {scored.length === 0 && <div className="sub">No measured score.</div>}
            {scored.map((s, i) => (
              <div key={s.label} className="nb-scope">
                <b className="mono">{scoreText(s.value, data.objective.unit)}</b>
                <i style={{ height: Math.max(4, (Math.abs(s.value) / max) * 60), animationDelay: `${i * 0.1}s` }} />
                <span>{s.label}</span>
              </div>
            ))}
          </div>
          {exp.note && <div className="sub nb-note">{exp.note}</div>}
        </div>
        {table ? (
          <div className="card">
            <div className="eyebrow ink">{table.title}</div>
            <table className="nb-table">
              <thead>
                <tr>
                  {table.columns.map((c, i) => (
                    <th key={i}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {table.rows.map((row, r) => (
                  <tr key={r}>
                    {row.map((cell, c) => (
                      <td key={c} className={c === 0 ? undefined : "mono"}>
                        {c === 0 ? cell : <b>{cell}</b>}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="card">
            <div className="eyebrow ink">Change</div>
            <div className="nb-change-text">{exp.change}</div>
            <div className="sub">Parent: {exp.parent ?? "—"}</div>
          </div>
        )}
      </div>
    </section>
  );
}

function Trajectory({
  data,
  selected,
  onRoute,
}: {
  data: Experiments;
  selected: string | null;
  onRoute: (patch: Partial<Route>) => void;
}) {
  const paths = trajectoryPaths(data.experiments, data.scopes);
  const goal = data.objective.goal;
  const layout = trajectoryLayout(data.experiments, paths, data.scopes, goal, BOX);
  const plotted = layout.paths.some(p => p.length > 0);
  const unit = data.objective.unit === "%" ? "%" : "";
  return (
    <div className="card nb-traj">
      <div className="eyebrow ink">Trajectory · {data.objective.label}</div>
      {!plotted ? (
        <div className="sub">No measured score.</div>
      ) : (
        <svg className="nb-chart" viewBox={`0 0 ${BOX.width} ${BOX.height}`} role="img" aria-label="Trajectory">
          {layout.ticks.map(v => (
            <g key={v}>
              <line className="nb-grid-line" x1={BOX.left} x2={BOX.width - BOX.right} y1={layout.y(v)} y2={layout.y(v)} />
              <text className="nb-axis" x={BOX.left - 6} y={layout.y(v) + 4} textAnchor="end">
                {v.toFixed(0)}
                {unit}
              </text>
            </g>
          ))}
          {goal !== null && layout.goalY !== null && (
            <g>
              <line className="nb-goal" x1={BOX.left} x2={BOX.width - BOX.right} y1={layout.goalY} y2={layout.goalY} />
              <text className="nb-axis" x={BOX.width - BOX.right} y={layout.goalY - 5} textAnchor="end">
                goal {goal}
                {unit}
              </text>
            </g>
          )}
          {layout.paths.map((path, k) => {
            if (path.length === 0) return null;
            const stroke = SERIES[k] ?? SERIES[0];
            const last = path[path.length - 1];
            return (
              <g key={k}>
                <path className="nb-path" d={path.map((q, i) => `${i === 0 ? "M" : "L"}${q.x},${q.y}`).join(" ")} style={{ stroke }} />
                {path.map(q => {
                  const on = q.id === selected;
                  return (
                    <circle
                      key={q.id}
                      className="nb-point"
                      role="button"
                      tabIndex={0}
                      cx={q.x}
                      cy={q.y}
                      r={on ? 6 : 4}
                      style={{ fill: on ? stroke : "#fffefc", stroke }}
                      onClick={() => onRoute({ exp: q.id })}
                      onKeyDown={ev => {
                        if (ev.key === "Enter" || ev.key === " ") onRoute({ exp: q.id });
                      }}
                    >
                      <title>{`${q.id} · ${scoreText(q.value, data.objective.unit)}`}</title>
                    </circle>
                  );
                })}
                <text className="nb-end" x={last.x + 10} y={last.y + 4} style={{ fill: stroke }}>
                  {last.id}
                </text>
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
}

function SectionsCard({ data }: { data: Experiments }) {
  return (
    <div className="card nb-lessons">
      {data.sections.map(section => (
        <div key={section.title} className="nb-section">
          <div className="eyebrow ink">{section.title}</div>
          <ul>
            {section.items.map((item, i) => (
              <li key={i}>
                {item.head && <b>{item.head} </b>}
                <span>{item.body}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
