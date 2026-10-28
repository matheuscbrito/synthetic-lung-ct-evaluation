// Generators › Benchmark (slide "Benchmark" dos mockups v3, sem cartões de KPI): tabela de versões com status por eixo,
// cartão de indicadores (testes de coorte primeiro) e cartão de transições com eixo, resumo e filtro.
// Tudo vem do contrato: eixos, status, indicadores, testes de coorte, rótulos das versões e dos itens.
import { useState, type CSSProperties, type ReactNode } from "react";
import { useContract } from "../contract/client";
import { signed, toneOf } from "../contract/format";
import type { Item, ItemsResponse, Runs, Schema, StatusKey, Transition, VersionInfo } from "../contract/types";
import { TONE_COLORS } from "../dataset/strip";
import type { Route } from "../route";
import { Seg } from "../ui/Seg";
import {
  axisStatuses,
  CHIP_AXES_MAX,
  clearDifferences,
  defaultCurrent,
  filterTransitions,
  indicatorDecimals,
  orderTransitions,
  orderVersions,
  RESULT_LABEL,
  resultStatus,
  scoreText,
  transitionSummary,
  type BenchBoard,
  type TransitionFilter,
} from "./bench";
import { GeneratorTabs } from "./GeneratorTabs";
import "./bench.css";

const CHANGE: Record<string, { mark: string; label: string; tone: "good" | "bad" | "neutral" }> = {
  improved: { mark: "▲", label: "Improved", tone: "good" },
  worsened: { mark: "▼", label: "Worsened", tone: "bad" },
  same: { mark: "＝", label: "Same", tone: "neutral" },
};

const statusLabel = (schema: Schema, k: StatusKey) => schema.statuses.find(s => s.key === k)?.label ?? k;

function Tag({ schema, status, label }: { schema: Schema; status: StatusKey; label?: string }) {
  const c = TONE_COLORS[toneOf(schema, status)];
  return (
    <span className="gb-pill" style={{ background: c.bg, color: c.fg }}>
      <i style={{ background: c.mark }} aria-hidden="true" />
      {label ?? statusLabel(schema, status)}
    </span>
  );
}

function StatusBar({ schema, counts }: { schema: Schema; counts: Partial<Record<StatusKey, number>> }) {
  const order = [...schema.statuses].sort((a, b) => a.severity - b.severity);
  const total = order.reduce((n, s) => n + (counts[s.key] ?? 0), 0) || 1;
  return (
    <div className="gb-sbar" role="img" aria-label={order.map(s => `${s.label} ${counts[s.key] ?? 0}`).join(", ")}>
      {order
        .filter(s => (counts[s.key] ?? 0) > 0)
        .map(s => (
          <i
            key={s.key}
            title={`${s.label} ${counts[s.key]}`}
            style={{ flex: (counts[s.key] ?? 0) / total, background: TONE_COLORS[s.tone].mark }}
          />
        ))}
    </div>
  );
}

export interface BenchmarkProps {
  schema: Schema;
  board: BenchBoard;
  baseline: string;
  /** Version compared with the baseline; undefined when the board has no other version. */
  current: string | undefined;
  axis: string;
  /** Transitions baseline → current on `axis`; null while loading. */
  transitions: Transition[] | null;
  /** Items of the current version by id (labels of the transitions list). */
  items: Record<string, Item>;
  /** Optimizer runs that exist (provenance link only for these). */
  runKeys: Set<string>;
  onRoute: (patch: Partial<Route>) => void;
}

export function Benchmark({ schema, board, baseline, current, axis, transitions, items, runKeys, onRoute }: BenchmarkProps) {
  const ds = schema.dataset;
  const noun = ds.item;
  const axes = schema.axes;
  const compact = axes.length > CHIP_AXES_MAX;
  const versions = orderVersions(board.versions, baseline);
  const shown = axisStatuses(board.versions, schema);
  const label = (name: string | undefined) => board.versions.find(v => v.name === name)?.label ?? name ?? "";
  const cur = board.versions.find(v => v.name === current);
  const good = schema.statuses.find(s => s.tone === "good") ?? schema.statuses[0];
  const indicators = new Map(schema.indicators.map(i => [i.key, i]));

  const [filter, setFilter] = useState<TransitionFilter>("all");
  const [allIndicators, setAllIndicators] = useState(false);

  const cols: CSSProperties = { gridTemplateColumns: `1.25fr repeat(${axes.length}, minmax(0, 1fr)) 1.5fr` };

  const table = (
    <div className="gb-table">
      <div className="gb-thead" style={cols}>
        <div>Generator</div>
        {axes.map(a => (
          <div key={a.key}>{a.label}</div>
        ))}
        <div>vs baseline</div>
      </div>
      {versions.map(v => {
        const vb = v.vs_baseline ?? [];
        const up = vb.filter(x => x.result === "improved").length;
        const dn = vb.filter(x => x.result === "worse").length;
        const run = v.provenance && runKeys.has(v.provenance.run) ? v.provenance.run : null;
        return (
          <div
            key={v.name}
            className={v.name === current ? "gb-trow on" : "gb-trow"}
            style={cols}
            role="button"
            tabIndex={0}
            aria-pressed={v.name === current}
            onClick={() => v.name !== baseline && onRoute({ version: v.name })}
            onKeyDown={e => {
              if ((e.key === "Enter" || e.key === " ") && v.name !== baseline) {
                e.preventDefault();
                onRoute({ version: v.name });
              }
            }}
          >
            <div>
              <b>{v.label ?? v.name}</b>
              {(v.subtitle || run) && (
                <div className="sub">
                  {v.subtitle}
                  {run && (
                    <button
                      type="button"
                      className="gb-otag"
                      onClick={e => {
                        e.stopPropagation();
                        onRoute({ tab: "runs", run });
                      }}
                    >
                      see in Optimizers ↗
                    </button>
                  )}
                </div>
              )}
            </div>
            {axes.map(a => {
              const counts = v.counts[a.key] ?? {};
              return (
                <div key={a.key}>
                  {compact ? (
                    <StatusBar schema={schema} counts={counts} />
                  ) : (
                    shown.map(k => {
                      const c = TONE_COLORS[toneOf(schema, k)];
                      return (
                        <span
                          key={k}
                          className="gb-cnt"
                          title={statusLabel(schema, k)}
                          style={{ background: c.bg, color: c.fg }}
                        >
                          {counts[k] ?? 0}
                        </span>
                      );
                    })
                  )}
                </div>
              );
            })}
            <div>
              {v.name === baseline ? (
                <span className="gb-pill gb-base">baseline</span>
              ) : v.vs_baseline ? (
                <>
                  <span className="gb-pill" style={{ background: TONE_COLORS.good.bg, color: TONE_COLORS.good.fg }}>
                    {up} better
                  </span>{" "}
                  <span
                    className="gb-pill"
                    style={dn ? { background: TONE_COLORS.bad.bg, color: TONE_COLORS.bad.fg } : undefined}
                  >
                    {dn} worse
                  </span>
                </>
              ) : (
                <span className="sub">n/a</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );

  const clear = cur ? clearDifferences(cur) : [];
  const cohortRows = (cur?.cohort ?? []).map((c, i) => {
    const test = schema.cohort_tests.find(t => t.key === c.test);
    return (
      <div key={`cohort-${i}`} className="gb-irow gb-cohort">
        <span>{test?.label ?? c.test}</span>
        <span className="mono">{c.detail.map(d => `${d.label} ${d.value}`).join(" · ")}</span>
        <Tag schema={schema} status={c.result.status} label={c.result.label} />
      </div>
    );
  });
  const gainText = (gain: number | null, ci: [number | null, number | null] | null, d: number) => {
    if (gain === null || !Number.isFinite(gain)) return "n/a";
    const [lo, hi] = ci ?? [null, null];
    const interval = lo !== null && hi !== null ? ` [${signed(lo, d)}, ${signed(hi, d)}]` : "";
    return `${signed(gain, d)}${interval}`;
  };
  const indicatorRows = clear.map(v => {
    const desc = indicators.get(v.indicator);
    return (
      <div key={v.indicator} className="gb-irow">
        <span>{desc?.label ?? v.indicator}</span>
        <span className="mono">{gainText(v.gain, v.ci, indicatorDecimals(desc?.min_change))}</span>
        <Tag schema={schema} status={resultStatus(v.result, schema)} label={RESULT_LABEL[v.result]} />
      </div>
    );
  });

  const scoreTable = (
    <div className="gb-scorewrap">
      <table className="gb-scores">
        <thead>
          <tr>
            <th>Indicator</th>
            <th>Ideal</th>
            {versions.map(v => (
              <th key={v.name}>{v.label ?? v.name}</th>
            ))}
            {cur && <th>{`Change vs ${label(baseline)}`}</th>}
          </tr>
        </thead>
        <tbody>
          {schema.indicators.map(ind => {
            const d = indicatorDecimals(ind.min_change);
            const gain = cur?.vs_baseline?.find(x => x.indicator === ind.key);
            return (
              <tr key={ind.key}>
                <td>
                  {ind.label}
                  <div className="sub">{ind.unit}</div>
                </td>
                <td className="mono">{ind.ideal}</td>
                {versions.map(v => (
                  <td key={v.name} className="mono">
                    {scoreText(v.scores?.[ind.key], d)}
                  </td>
                ))}
                {cur && (
                  <td className="mono">
                    {gain ? (
                      <>
                        {gainText(gain.gain, gain.ci, d)}{" "}
                        <Tag schema={schema} status={resultStatus(gain.result, schema)} label={RESULT_LABEL[gain.result]} />
                      </>
                    ) : (
                      "n/a"
                    )}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );

  const indicatorsCard = (
    <div className="card gb-irows">
      <div className="gb-ihead">
        <div className="eyebrow ink">
          {allIndicators
            ? "All indicators · score per version, 95% CI"
            : `${label(current)} · indicators with a clear difference`}
        </div>
        <button type="button" className="gb-toggle" aria-pressed={allIndicators} onClick={() => setAllIndicators(x => !x)}>
          All indicators
        </button>
      </div>
      {allIndicators ? (
        scoreTable
      ) : !cur ? (
        <div className="sub gb-empty">No other version to compare with {label(baseline)}.</div>
      ) : (
        <>
          {cohortRows}
          {indicatorRows.length ? indicatorRows : <div className="sub gb-empty">No clear difference.</div>}
        </>
      )}
    </div>
  );

  const summary = transitions ? transitionSummary(transitions) : null;
  const listed = transitions ? orderTransitions(filterTransitions(transitions, filter), schema) : [];
  const filters: { value: TransitionFilter; label: string }[] = [
    { value: "all", label: "All" },
    { value: "improved", label: "Improved" },
    { value: "worsened", label: "Worsened" },
    { value: "became", label: `Became ${good.label.toLowerCase()}` },
  ];

  let transitionBody: ReactNode;
  if (!cur) transitionBody = <div className="sub gb-empty">No other version to compare with {label(baseline)}.</div>;
  else if (!transitions) transitionBody = <div className="sub gb-empty">Loading…</div>;
  else if (!listed.length)
    transitionBody = (
      <div className="sub gb-empty">
        {filter === "all" ? `No ${noun.singular} changed verdict.` : `No ${noun.singular} in this filter.`}
      </div>
    );
  else
    transitionBody = listed.map(x => {
      const it = items[x.id];
      const chg = CHANGE[x.change] ?? CHANGE.same;
      return (
        <div
          key={x.id}
          className="gb-xr"
          role="button"
          tabIndex={0}
          title={x.id}
          onClick={() => onRoute({ section: "dataset", tab: "item", item: x.id, version: current })}
          onKeyDown={e => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              onRoute({ section: "dataset", tab: "item", item: x.id, version: current });
            }
          }}
        >
          <span>
            <b>{it?.label ?? `${noun.singular} ${listed.indexOf(x) + 1}`}</b>
            {ds.group_by && it?.group && <span className="sub"> {it.group}</span>}
          </span>
          <span className="gb-ba">
            <Tag schema={schema} status={x.before} />
            <em>→</em>
            <Tag schema={schema} status={x.after} />
          </span>
          <span className="gb-chg" style={{ color: TONE_COLORS[chg.tone].fg }}>
            {chg.mark} {chg.label}
          </span>
        </div>
      );
    });

  const transitionsCard = (
    <div className="card gb-right">
      <div className="gb-ghead">
        <div className="eyebrow ink">
          Transitions · {label(baseline)} → {cur ? label(current) : "–"}
        </div>
        <Seg<string>
          small
          label="Transition axis"
          value={axis}
          onChange={a => onRoute({ axis: a })}
          options={axes.map(a => ({ value: a.key, label: a.label }))}
        />
      </div>
      {summary && cur && (
        <div className="gb-tsum">
          <b style={{ color: TONE_COLORS.bad.fg }}>▼ {summary.worsened}</b> worsened ·{" "}
          <b style={{ color: TONE_COLORS.good.fg }}>▲ {summary.improved}</b> improved ·{" "}
          <b>{summary.becameApproved}</b> became {good.label.toLowerCase()}{" "}
          <span className="sub">of {board.n_items}</span>
        </div>
      )}
      <Seg<TransitionFilter> small label="Transition filter" value={filter} onChange={setFilter} options={filters} />
      <div className="gb-xtable">{transitionBody}</div>
    </div>
  );

  return (
    <div className="gb">
      <div className="head">
        <div>
          <div className="eyebrow">Generators · vs baseline</div>
          <h1>Benchmark</h1>
          <div className="sub">
            {`Same ${board.n_items} ${noun.plural} · ${board.versions.length} versions`}
            {cur ? ` · ${label(current)} vs ${label(baseline)}` : ""}
          </div>
        </div>
        <div className="head-right">
          <GeneratorTabs
            active="bench"
            addons={schema.addons}
            onSelect={tab => tab !== "bench" && onRoute({ tab })}
          />
          {schema.datasets.length > 1 && (
            <div className="dsw">
              <Seg<string>
                small
                label="Dataset"
                value={ds.key}
                onChange={key =>
                  onRoute({ dataset: key, version: undefined, baseline: undefined, axis: undefined, item: undefined, items: undefined })
                }
                options={schema.datasets.map(d => ({ value: d.key, label: d.label }))}
              />
            </div>
          )}
          <label className="ui-chip gb-ver">
            <span>vs</span>
            <select aria-label="Baseline" value={baseline} onChange={e => onRoute({ baseline: e.target.value })}>
              {board.versions.map(v => (
                <option key={v.name} value={v.name}>
                  {v.label ?? v.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="gb-cols">
        <div className="gb-left">
          {table}
          <div className="sub gb-caption">
            {shown.map(k => statusLabel(schema, k)).join(" · ")} counts per axis
            {cur ? ` · indicators compare ${label(current)} with ${label(baseline)}, 95% CI` : ""}
          </div>
          {indicatorsCard}
        </div>
        {transitionsCard}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- ligação com a API

function Message({ text, error }: { text: string; error?: boolean }) {
  return <p className={error ? "error" : "sub"}>{text}</p>;
}

type Loaded = Omit<BenchmarkProps, "runKeys">;

/** Optimizer run keys, fetched only when the Optimizers add-on exists. */
function WithRuns({ props }: { props: Loaded }) {
  const runs = useContract<Runs>("/api/runs", {});
  // sem a lista de execuções o link de origem some, mas o benchmark continua
  const keys = new Set((runs.data?.runs ?? []).map(r => r.key));
  return <Benchmark {...props} runKeys={keys} />;
}

function Ready({ props }: { props: Loaded }) {
  return props.schema.addons.optimizers ? <WithRuns props={props} /> : <Benchmark {...props} runKeys={new Set()} />;
}

/** Transitions baseline → current on the axis, and the current version's items for their labels. */
function WithCurrent({ props, current }: { props: Omit<Loaded, "transitions" | "items" | "current">; current: string }) {
  const dataset = props.schema.dataset.key;
  const transitions = useContract<Transition[]>("/api/v2/transitions", {
    dataset,
    before: props.baseline,
    after: current,
    axis: props.axis,
  });
  const items = useContract<ItemsResponse>("/api/items", { dataset, version: current });
  const byId = items.data ? Object.fromEntries(items.data.items.map(i => [i.id, i])) : {};
  // a lista só aparece com os rótulos dos itens; erro de transições vira lista vazia com a tela intacta
  const list = transitions.error ? [] : transitions.data && items.data ? transitions.data : null;
  return <Ready props={{ ...props, current, transitions: list, items: byId }} />;
}

function WithBoard({ schema, baseline, route, onRoute }: { schema: Schema; baseline: string } & PageProps) {
  const board = useContract<BenchmarkProps["board"]>("/api/v2/board", { dataset: schema.dataset.key, baseline });
  if (board.error) return <Message error text={board.error} />;
  if (!board.data) return <Message text="Loading…" />;
  const current = defaultCurrent(board.data.versions, baseline, route.version);
  const axis = schema.axes.some(a => a.key === route.axis) ? route.axis! : schema.axes[0]?.key ?? "";
  const base = { schema, board: board.data, baseline, axis, onRoute };
  if (!current) return <Ready props={{ ...base, current: undefined, transitions: [], items: {} }} />;
  return <WithCurrent props={base} current={current} />;
}

interface PageProps {
  route: Route;
  onRoute: (patch: Partial<Route>) => void;
}

/** Benchmark wired to the API: versions validate the baseline, then board, transitions, items and runs. */
export function GeneratorBenchmark({ schema, route, onRoute }: { schema: Schema } & PageProps) {
  const versions = useContract<VersionInfo[]>("/api/v2/versions", { dataset: schema.dataset.key });
  if (versions.error) return <Message error text={versions.error} />;
  if (!versions.data) return <Message text="Loading…" />;
  const names = versions.data.map(v => v.name);
  const fallback = names.includes(schema.dataset.default_baseline) ? schema.dataset.default_baseline : names[0];
  const baseline = route.baseline && names.includes(route.baseline) ? route.baseline : fallback;
  if (!baseline) return <Message text="No versions in this dataset yet." />;
  return <WithBoard schema={schema} baseline={baseline} route={route} onRoute={onRoute} />;
}
