// Generators › Optimizers (slide "Optimizers" dos mockups v3, sem cartões): curvas de melhor score por orçamento
// à esquerda; à direita, a tabela de ranking e os passos da execução selecionada. Clicar numa linha destaca a curva
// e apaga as demais (18%). Tudo vem de /api/runs: colunas de parâmetros, faixa do eixo y e linha de meta.
import type { CSSProperties, KeyboardEvent } from "react";
import { useContract } from "../contract/client";
import { toneOf, ticks } from "../contract/format";
import type { Runs, Schema } from "../contract/types";
import { TONE_COLORS } from "../dataset/strip";
import type { Route } from "../route";
import { spreadLabels } from "../components/labelSpread";
import { GeneratorTabs } from "./GeneratorTabs";
import { paramText, rankRuns, runScore, stepColumns, unitSuffix } from "./runs";
import "./Optimizers.css";

const DIM = 0.18;
const LABEL_GAP = 15;
const W = 640;
const H = 500;
const PL = 52;
const PR = 170;
const PT = 14;
const PB = 52;

export interface OptimizersProps {
  schema: Schema;
  runs: Runs;
  /** Route's `run`: the selected run; when it names a run, the other curves are dimmed. */
  run: string | undefined;
  onRoute: (patch: Partial<Route>) => void;
}

interface Point {
  x: number;
  y: number | null;
}

/** Step path (H then V) through the finite points; a missing score breaks the line, its budget stays in place. */
function stepPath(curve: Point[], X: (v: number) => number, Y: (v: number) => number): string {
  let d = "";
  let pen = false;
  for (const p of curve) {
    if (p.y === null || !Number.isFinite(p.y)) {
      pen = false;
      continue;
    }
    d += pen ? ` H${X(p.x).toFixed(1)} V${Y(p.y).toFixed(1)}` : `M${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`;
    pen = true;
  }
  return d;
}

export function Optimizers({ schema, runs, run, onRoute }: OptimizersProps) {
  const obj = runs.objective;
  const unit = obj.unit;
  const bax = runs.budget_axis.label;
  const byKey = new Map(runs.runs.map(r => [r.key, r]));
  const ranked = rankRuns(runs.runs);
  const focused = run !== undefined && byKey.has(run);
  const selectedKey = focused ? run : ranked[0]?.key;
  const selected = selectedKey === undefined ? undefined : byKey.get(selectedKey);

  const head = (
    <div className="head">
      <div>
        <div className="eyebrow">Generators · optimizers</div>
        <h1>Optimizers</h1>
        <div className="sub">
          Searches for generator settings · {obj.label}
          {runs.sources.length > 0 && ` · source ${runs.sources.map(s => s.label).join(" · ")}`}
        </div>
      </div>
      <div className="head-right">
        <GeneratorTabs
          active="runs"
          addons={schema.addons}
          onSelect={tab => tab !== "runs" && onRoute({ tab })}
        />
      </div>
    </div>
  );

  if (runs.runs.length === 0 || !selected) {
    return (
      <div className="opt">
        {head}
        <p className="sub opt-empty">No optimizer runs yet</p>
      </div>
    );
  }

  // ---- curva: eixo x do orçamento, y da faixa dos dados e da meta (só quando existe)
  const xmax = Math.max(1, ...runs.runs.flatMap(r => r.curve.map(p => p.x)));
  const ys = runs.runs.flatMap(r => r.curve.map(p => p.y)).filter((y): y is number => y !== null && Number.isFinite(y));
  if (obj.goal !== null) ys.push(obj.goal);
  const lo = Math.min(0, ...ys);
  let hi = Math.max(0, ...ys);
  if (hi <= lo) hi = lo + 1;
  const top = lo + (hi - lo) * 1.08;
  const yt = ticks(lo, top);
  const ymin = yt[0] ?? lo;
  const ymax = yt[yt.length - 1] ?? top;
  const span = ymax - ymin || 1;
  const X = (v: number) => PL + (v / xmax) * (W - PL - PR);
  const Y = (v: number) => PT + (1 - (v - ymin) / span) * (H - PT - PB);

  const ends = ranked.flatMap(r => {
    const curve = byKey.get(r.key)!.curve;
    const last = [...curve].reverse().find(p => p.y !== null && Number.isFinite(p.y));
    return last ? [{ key: r.key, label: r.label, color: r.color, x: last.x, y: last.y as number }] : [];
  });
  const labelYs = spreadLabels(ends.map(e => Y(e.y)), LABEL_GAP);

  const curve = (
    <svg className="spec opt-curve" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Best ${obj.label} by ${bax}`}>
      {yt.map(t => (
        <g key={`y${t}`}>
          <line x1={PL} x2={W - PR} y1={Y(t)} y2={Y(t)} className="grid" />
          <text x={PL - 8} y={Y(t) + 4} className="ax" textAnchor="end">
            {paramText(t)}
            {unit === "%" ? "%" : ""}
          </text>
        </g>
      ))}
      {ticks(0, xmax)
        .filter(t => t <= xmax)
        .map(t => (
          <text key={`x${t}`} x={X(t)} y={H - 30} className="ax" textAnchor="middle">
            {paramText(t)}
          </text>
        ))}
      <text x={(PL + W - PR) / 2} y={H - 8} className="ax" textAnchor="middle">
        {bax}
      </text>
      {obj.goal !== null && (
        <g className="goal-rule">
          <line x1={PL} x2={W - PR} y1={Y(obj.goal)} y2={Y(obj.goal)} className="nyq" style={{ stroke: "#16150f" }} />
          <text x={PL + 6} y={Y(obj.goal) - 5} className="ax">
            goal {paramText(obj.goal)}
            {unitSuffix(unit)}
          </text>
        </g>
      )}
      {ranked.map(r => {
        const run1 = byKey.get(r.key)!;
        const color = r.color;
        const opacity = focused && r.key !== selectedKey ? DIM : 1;
        const end = ends.findIndex(e => e.key === r.key);
        const d = stepPath(run1.curve, X, Y);
        return (
          <g key={r.key} className="opt-run" data-run={r.key} style={{ opacity, transition: "opacity .25s" }}>
            {d && <path d={d} className="line" style={{ stroke: color }} />}
            {end >= 0 && (
              <>
                <line
                  x1={W - PR + 4}
                  x2={W - PR + 12}
                  y1={labelYs[end]}
                  y2={labelYs[end]}
                  style={{ stroke: color, strokeWidth: 2 }}
                />
                <text x={W - PR + 16} y={labelYs[end] + 4} className="lab">
                  {r.label} {runScore(ends[end].y, unit)}
                </text>
              </>
            )}
          </g>
        );
      })}
    </svg>
  );

  // ---- ranking: uma linha por execução; melhores parâmetros no título da linha
  const paramLabel = (key: string) => runs.params.find(p => p.key === key)?.label ?? key;
  const rankRows = ranked.map(r => {
    const raw = byKey.get(r.key)!;
    const on = r.key === selectedKey;
    const bestConfig = runs.params
      .filter(p => p.key in raw.best_params)
      .map(p => `${p.label} ${paramText(raw.best_params[p.key])}`)
      .join(" · ");
    const b = raw.summary.budget;
    const choose = () => onRoute({ run: r.key });
    const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        choose();
      }
    };
    return (
      <div
        key={r.key}
        className={on ? "opt-row on" : "opt-row"}
        role="button"
        tabIndex={0}
        aria-pressed={on}
        title={bestConfig ? `Best configuration: ${bestConfig}` : undefined}
        onClick={choose}
        onKeyDown={onKey}
      >
        <span className="opt-name">
          <i className="opt-key" style={{ background: r.color }} aria-hidden="true" />
          {r.label}
        </span>
        <span className="mono opt-best">{runScore(r.best, unit)}</span>
        <span className="mono">{r.toBest ?? "n/a"}</span>
        <span className="mono">{r.evaluated}</span>
        <span className="mono">{b ? `${r.used}/${b}` : `${r.used}`}</span>
      </div>
    );
  });

  // ---- passos da execução selecionada: colunas dinâmicas (Stage e W / L só quando existem)
  const cols = stepColumns(selected, runs.params);
  const grid: CSSProperties = {
    gridTemplateColumns: [
      "44px",
      cols.stage ? "54px" : "",
      ...cols.params.map(() => "minmax(0,1fr)"),
      "84px",
      cols.wl ? "54px" : "",
    ]
      .filter(Boolean)
      .join(" "),
  };
  const steps = selected.steps.map((st, i) => {
    const tone = TONE_COLORS[toneOf(schema, st.outcome.status)];
    return (
      <div key={`${st.id}-${i}`} className={st.is_best ? "opt-step best" : "opt-step"} style={grid}>
        <span className="mono">#{st.id}</span>
        {cols.stage && <span>{st.stage ?? ""}</span>}
        {cols.params.map(p => (
          <span key={p.key} className="mono opt-prm">
            {paramText(st.params[p.key])}
          </span>
        ))}
        <span className="mono opt-chip" title={st.outcome.label} style={{ background: tone.bg, color: tone.fg }}>
          {runScore(st.score, unit)}
          {st.is_best ? " ★" : ""}
        </span>
        {cols.wl && (
          <span className="mono">
            {paramText(st.wins)}/{paramText(st.losses)}
          </span>
        )}
      </div>
    );
  });

  return (
    <div className="opt">
      {head}
      <div className="opt-cols">
        <section className="opt-panel opt-chart">
          <div className="opt-eyebrow">
            Best {obj.label.toLowerCase()} · by {bax}
          </div>
          {curve}
        </section>
        <div className="opt-right">
          <section className="opt-panel">
            <div className="opt-rankhead">
              <span>Optimizer</span>
              <span>Best</span>
              <span title={`${bax} until the best`}>To best</span>
              <span title="configurations evaluated">Configs</span>
              <span title={`${bax} / budget`}>Used</span>
            </div>
            {rankRows}
          </section>
          <section className="opt-panel opt-steps">
            <div className="opt-eyebrow">Steps · {selected.label}</div>
            <div className="opt-steps-head" style={grid}>
              <span>#</span>
              {cols.stage && <span>Stage</span>}
              {cols.params.map(p => (
                <span key={p.key}>{paramLabel(p.key)}</span>
              ))}
              <span title={obj.label}>Score</span>
              {cols.wl && <span>W / L</span>}
            </div>
            {steps.length > 0 ? <div className="opt-steps-body">{steps}</div> : <p className="sub">No steps recorded.</p>}
          </section>
        </div>
      </div>
    </div>
  );
}

interface PageProps {
  route: Route;
  onRoute: (patch: Partial<Route>) => void;
}

/** Optimizers wired to the API: `/api/runs` once, then the screen. */
export function GeneratorOptimizers({ schema, route, onRoute }: { schema: Schema } & PageProps) {
  const runs = useContract<Runs>("/api/runs", {});
  if (runs.error) return <p className="error">{runs.error}</p>;
  if (!runs.data) return <p className="sub">Loading…</p>;
  return <Optimizers schema={schema} runs={runs.data} run={route.run} onRoute={onRoute} />;
}
